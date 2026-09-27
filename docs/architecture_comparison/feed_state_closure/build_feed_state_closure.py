#!/usr/bin/env python3
"""W1 feed-state closure v1 (follow-on fo_feed_state_closure; trigger T_PIVOT_FEED_STATE_CLOSURE; owner disposition
od_hardware_pivot, docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json).

Converts 180 / 200 / 230 km x low / mean / high solar activity (frozen NRLMSIS 2.1)
    atmosphere -> intake (frozen TPMC ROM) -> compressor (DragCompressor) -> buffer (Reservoir) -> valve
into valve-outlet states {m_dot_s, P_feed, T_feed, x_s} (ICD IF-A5) for a small set of explicit, labelled DESIGN
CANDIDATES, and from them a PROPOSED ground TEST-POINT set for the common-hardware experiment (Phase 1 Hall-only
sustainment knee on N2, Phase 2 common-condition comparison, Phase 3 absolute demonstration), each test point traceable
to a design candidate and an altitude / solar case.

What it is: a DRAFT for owner review that makes the lane-16 valve-outlet TBD (DI-1) evaluable under stated, PROPOSED
design candidates, with the design-input inventory, dominant sensitivities and the owner decisions needed to freeze
DI-1. What it is not: a design baseline, a Hall prediction, an architecture ranking or a model change. No existing module
is modified or wired; no frozen dataset is rebuilt; no Hall transport closure, ensemble member, screening candidate or
P5 calibration-nuisance variable enters any value. Every design input carries a source and an evidence class (the
candidate values are 'assumed' / PROPOSED unless stated); a missing input raises (lane-16 contract, reused).

Chain: the design-conditional chain of scripts/architecture/build_feed_envelope.py (lane 16, merged; `run_chain`,
`frozen_state`, `validate_design_inputs`) is loaded read-only by path and used unchanged; it imports abep_sim.intake,
intake_tpmc, compressor, reservoir and atmosphere (frozen dataset forced and hash-checked). abep_sim.intake.collection
is called directly only for the intake drag diagnostic and the area sizing rule.

Deterministic, no Julia, ~15-25 s single-threaded.

Usage:
  python docs/architecture_comparison/feed_state_closure/build_feed_state_closure.py          # (re)write outputs
  python docs/architecture_comparison/feed_state_closure/build_feed_state_closure.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT_DIR_REL = "docs/architecture_comparison/feed_state_closure"
SCRIPT_REL = f"{OUT_DIR_REL}/build_feed_state_closure.py"
JSON_NAME = "feed_state_closure_v1.json"
SCHEMA_NAME = "feed_state_closure_v1.schema.json"
MD_NAME = "FEED_STATE_CLOSURE.md"
LANE16_SCRIPT_REL = "scripts/architecture/build_feed_envelope.py"
DECISION_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
LANE25_DRAFT_REL = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
SCHEMA_ID = "feed_state_closure_v1"
VERSION = "1.0.0"
BASE_COMMIT = "510e464fb8e128e4cf3325572a4d36ad33a4899d"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
ALTITUDES_KM = (180.0, 200.0, 230.0)
LEVELS = ("low", "mean", "high")
AIR = ("O", "N2", "O2")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
CONVENTION = "chain_freestream_split"          # lane-16 primary convention (system.evaluate); FE-05 alternative below

# --- PROPOSED design-candidate axes (owner review). Values not in the RFP are PROPOSED.
DESIGN_CASE = (200.0, "mean")                 # PROPOSED design case for the area sizing rule (mid-envelope altitude)
SIZING_RULES = {
    "S12": {"thrust_attr": "thrust_min_mN",
            "label": "intake-only drag at the design case = RFP minimum thrust (12 mN)"},
    "S25": {"thrust_attr": "thrust_max_mN",
            "label": "intake-only drag at the design case = RFP maximum thrust (25 mN)"},
}
GEOMETRIES = {
    "G03": {"L_over_d": 3.0, "phi": 0.9, "label": "short channels: highest forward transmission, lowest passive CR"},
    "G10": {"L_over_d": 10.0, "phi": 0.9, "label": "intermediate channels"},
    "G20": {"L_over_d": 20.0, "phi": 0.9, "label": "long channels: lowest forward transmission, highest passive CR"},
}
SETPOINT_LADDER_PA = (0.05, 0.1, 0.2, 0.3, 0.5, 1.0)   # PROPOSED valve-outlet pressure ladder (0.05 = HISTORY v1.0 ref.)
NOMINAL_SCATTERING = "maxwell"
NOMINAL_ACCOMMODATION = 1.0
NOMINAL_OFF_AXIS_DEG = 0.0

# one-at-a-time sensitivity variants, applied at each candidate's nominal setpoint (area held at the nominal value:
# a built intake does not change size)
SENSITIVITIES = (
    {"id": "SEN-ALPHA-0.8", "axis": "intake surface state", "override": {"intake.accommodation": 0.8},
     "source": "abep_sim/uq_modular.py PRIORS['accommodation'] mode 0.8 (code prior, no cited source: verify)"},
    {"id": "SEN-ALPHA-0.5", "axis": "intake surface state", "override": {"intake.accommodation": 0.5},
     "source": "abep_sim/intake.py IntakeParams.accommodation default 0.5 (no cited source); frozen grid node"},
    {"id": "SEN-THETA-2", "axis": "pointing", "override": {"intake.off_axis_deg": 2.0},
     "source": "frozen TPMC grid node theta = 2 deg (PROPOSED pointing-error level)"},
    {"id": "SEN-THETA-5", "axis": "pointing", "override": {"intake.off_axis_deg": 5.0},
     "source": "frozen TPMC grid node theta = 5 deg (largest pointing error on the grid)"},
    {"id": "SEN-CLL", "axis": "gas-surface kernel", "override": {"intake.scattering": "cll"},
     "source": "frozen TPMC surface subset 'cll' (alpha_n = alpha_t = 1.0)"},
    {"id": "SEN-PLENUM-T-300", "axis": "plenum gas temperature", "override": {"plenum.T_gas_K": 300.0},
     "source": "PROPOSED lower plenum temperature (assumed; ICD G-07 two-temperature inconsistency)"},
    {"id": "SEN-ROTOR-TI", "axis": "compressor rotor material", "override": {"compressor.rotor_material": "Ti6Al4V"},
     "source": "abep_sim/compressor.py DragCompressor.rotor_material default (no cited source)"},
    {"id": "SEN-WALL-TI", "axis": "buffer wall material", "override": {"chamber.wall_material": "Ti6Al4V",
                                                                        "chamber.upstream_material": "Ti6Al4V"},
     "source": "abep_sim/reservoir.py Reservoir.wall_material / upstream_material defaults (no cited source)"},
    {"id": "SEN-SPECIES-RESOLVED", "axis": "collected-flow composition convention", "override": {},
     "convention": "species_resolved_surface",
     "source": "lane 16 FE-05 / ICD G-02: per-species eta_c of the same frozen surface"},
)
KNEE_LEVELS_FALLBACK = 5
SCCM_P0_PA = 101325.0                          # standard-condition definition used for the sccm conversion
SCCM_T0_K = 273.15                             # (0 degC, 1 atm); MFC vendors use other references: verify per MFC

REFERENCES = {
    "REF-ANDREUSSI2022": {
        "citation": "T. Andreussi, E. Ferrato, V. Giannetti, 'A review of air-breathing electric propulsion: from mission "
                    "studies to technology verification', Journal of Electric Propulsion 1, 31 (2022)",
        "doi": "10.1007/s44205-022-00024-9",
        "accessed": "open-access PDF https://www.iris.sssup.it/retrieve/ea75eb42-2e80-462b-be1e-588ed43871e3/"
                    "Andreussi%20et.al.%202022.pdf (full text read 2026-09-27)",
        "access": "full_text_open",
        "note": "secondary source (review); the primary references it cites were not accessed: verify before use as "
                "design evidence"},
    "REF-ROMANO2021": {
        "citation": "F. Romano et al., 'Intake design for an Atmosphere-Breathing Electric Propulsion System (ABEP)', "
                    "Acta Astronautica 187 (2021)",
        "doi": "10.1016/j.actaastro.2021.06.033",
        "accessed": "arXiv abstract page https://arxiv.org/abs/2106.15912 (2026-09-27)",
        "access": "abstract_only",
        "note": "abstract-only; body not read"},
}

COMPARABLES = (
    {"id": "LIT-01", "ref": "REF-ANDREUSSI2022", "where": "Table 1, p. 8",
     "statement": "ABEP platform concepts in the literature list frontal areas A_f from 0.01 to 1.5 m^2 and drag "
                  "coefficients C_D from 2 to 6 (e.g. Romano: 150-250 km, A_f 1 m^2, C_D 2.2; Diamant: 200 km, "
                  "0.5 m^2, C_D 2.2; Shabshelowitz: 180-200 km, 0.36 m^2)",
     "relevance": "range check for the candidate intake areas (sizing rule SR-DRAG); concept studies, not hardware",
     "evidence_class": "inferred", "role": "context_only"},
    {"id": "LIT-02", "ref": "REF-ANDREUSSI2022", "where": "Table 2, p. 15",
     "statement": "published intake studies report collection efficiencies of 0.25-0.45 (JAXA, passive, Maxwell, "
                  "ducted), 0.28-0.32 (SITAEL/ESA/VKI, passive, diffuse, ducted), 0.31-0.45 (IRS, passive, diffuse, "
                  "ducted) and 0.59-0.94 (IRS, specular, no ducts)",
     "relevance": "cross-check of the frozen TPMC eta_c definition (finding FC-02); not a calibration target",
     "evidence_class": "model-derived", "role": "context_only"},
    {"id": "LIT-03", "ref": "REF-ROMANO2021", "where": "abstract",
     "statement": "intake designs for 150-250 km: fully diffuse concept eta_c < 0.46, fully specular concept "
                  "eta_c < 0.94; diffuse-based intakes depend strongly on flow misalignment",
     "relevance": "cross-check of the frozen TPMC eta_c (finding FC-02) and of the pointing sensitivity",
     "evidence_class": "model-derived", "role": "context_only"},
    {"id": "LIT-04", "ref": "REF-ANDREUSSI2022", "where": "Table 3, p. 22",
     "statement": "electric thrusters tested with atmospheric propellants used N2, N2/O2, air/Xe and N2/O2/Ar feeds",
     "relevance": "ground practice for the N2-first and N2/O2 surrogate test points; performance values in that "
                  "table are NOT used (no literature performance source enters this document)",
     "evidence_class": "measured", "role": "context_only"},
    {"id": "LIT-05", "ref": "REF-ANDREUSSI2022", "where": "p. 23",
     "statement": "PPS1350-TSD Hall thruster tested on pure N2 at 2.3-2.85 mg/s and on an N2/O2 mixture down to "
                  "2.1 mg/s; cathode/neutralizer always supplied with xenon; post-test anode oxidation observed",
     "relevance": "precedent for N2 then N2/O2 anode feeds with a Xe cathode; O2 materials compatibility of H-1/C-1 "
                  "(W3 hardware lane)",
     "evidence_class": "measured", "role": "context_only"},
    {"id": "LIT-06", "ref": "REF-ANDREUSSI2022", "where": "p. 24",
     "statement": "SITAEL HT5k operated on a 0.56 N2 / 0.44 O2 mixture as a particle flow generator for ABEP "
                  "testing (anode 4.3-4.7 mg/s)",
     "relevance": "N2/O2 bottle mixtures are established ground surrogates",
     "evidence_class": "measured", "role": "context_only"},
    {"id": "LIT-07", "ref": "REF-ANDREUSSI2022", "where": "p. 25",
     "statement": "Busek fed a Hall thruster with an 'air simulant' of 68.3 % N2, 6.7 % O2 and 25 % Ar, argon "
                  "chosen for its similarities with atomic oxygen",
     "relevance": "only published atomic-O surrogate practice found; not proposed here (surrogate S-AR, section 9)",
     "evidence_class": "measured", "role": "context_only"},
    {"id": "LIT-08", "ref": "REF-ANDREUSSI2022", "where": "p. 26",
     "statement": "a 38 mm Hall thruster was tested with air and a 2-to-1 N2/O2 mixture at total flows of 0.8, 0.9 "
                  "and 1 mg/s (cathode 0.19 mg/s Xe)",
     "relevance": "sub-mg/s atmospheric-gas Hall operation has published precedent; context for the flow ladder",
     "evidence_class": "measured", "role": "context_only"},
)


class FeedClosureError(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------------------- helpers
def _load_lane16():
    path = REPO / LANE16_SCRIPT_REL
    if not path.exists():
        raise FeedClosureError(f"{LANE16_SCRIPT_REL} (lane 16 feed envelope) is required and was not found")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("_lane16_build_feed_envelope", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def case_id(alt: float, lvl: str) -> str:
    return f"alt{int(alt)}_{lvl}"


def fmt(x, d=4) -> str:
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if x == 0:
        return "0"
    return f"{x:.{d}g}"


def sccm_molecules_per_s() -> float:
    from abep_sim.constants import K_B
    return SCCM_P0_PA * 1e-6 / (K_B * SCCM_T0_K) / 60.0


def ground_flows(mdot_s: dict) -> dict:
    """Ground bottle equivalents of a valve-outlet state (O supplied as O2 at equal oxygen-element mass)."""
    from abep_sim.constants import M_SPECIES as M
    n_sccm = sccm_molecules_per_s()
    tot = sum(mdot_s.values())
    o_elem = mdot_s["O"] + mdot_s["O2"]
    part_flight = sum(mdot_s[s] / M[s] for s in AIR)
    part_ground = mdot_s["N2"] / M["N2"] + o_elem / M["O2"]
    return {
        "N2_only_mass_equivalent": {"mdot_N2_kgps": tot, "sccm_N2": tot / M["N2"] / n_sccm},
        "N2_only_particle_equivalent": {"mdot_N2_kgps": part_flight * M["N2"], "sccm_N2": part_flight / n_sccm},
        "air_surrogate_N2_O2": {"mdot_N2_kgps": mdot_s["N2"], "mdot_O2_kgps": o_elem,
                                "sccm_N2": mdot_s["N2"] / M["N2"] / n_sccm, "sccm_O2": o_elem / M["O2"] / n_sccm,
                                "w_O2": o_elem / tot, "w_N2": mdot_s["N2"] / tot,
                                "particle_flow_ratio_ground_over_flight": part_ground / part_flight},
    }


# ------------------------------------------------------------------------------------------------ design candidates
def code_defaults(fe) -> dict:
    return {"ip": fe._ast_class_defaults("abep_sim/intake.py", "IntakeParams"),
            "cp": fe._ast_class_defaults("abep_sim/intake.py", "CompressorParams"),
            "dc": fe._ast_class_defaults("abep_sim/compressor.py", "DragCompressor"),
            "rv": fe._ast_class_defaults("abep_sim/reservoir.py", "Reservoir"),
            "sf": fe._ast_function_defaults("abep_sim/compressor.py", "size_for", cls="DragCompressor"),
            "cfg": fe._ast_class_defaults("abep_sim/system.py", "Config")}


def drag_per_m2(atm: dict, L: float, phi: float, alpha: float, theta: float, scattering: str) -> dict:
    from abep_sim.intake import IntakeParams, collection
    ip = IntakeParams(area_m2=1.0, accommodation=alpha, off_axis_deg=theta, scattering=scattering, L_over_d=L,
                      phi=phi, use_tpmc=True)
    c = collection(ip, atm)
    return {"drag_N_per_m2": c["drag_N"], "C_D": c["C_D"], "eta_c": c["eta_c"], "CR_passive": c["passive_override"]}


def candidate_design_inputs(fe, d: dict, cid: str, geom: dict, area: float, area_src: str, setpoint: float) -> dict:
    """lane-16 feed_design_inputs_v1 document for one candidate at one valve setpoint (validated by lane 16)."""
    E = {}

    def put(name, value, source, ev, note=None):
        e = {"value": value, "source": source, "evidence_class": ev}
        if note:
            e["note"] = note
        E[name] = e

    P = "PROPOSED for owner review (fo_feed_state_closure)"
    put("intake.area_m2", area, area_src, "model-derived")
    put("intake.L_over_d", geom["L_over_d"], f"{P}: geometry {cid.split('-')[2]} (frozen TPMC grid node)", "assumed")
    put("intake.phi", geom["phi"], f"{P}: frozen TPMC grid maximum open-area fraction", "assumed")
    put("intake.accommodation", NOMINAL_ACCOMMODATION,
        f"{P}: fully diffuse surface (conservative end of the frozen grid); abep_sim/intake.py IntakeParams comment "
        "'AO ageing pushes ->1' (no cited source: verify)", "assumed")
    put("intake.off_axis_deg", NOMINAL_OFF_AXIS_DEG, f"{P}: nominal pointing (sensitivity to 2 and 5 deg)", "assumed")
    put("intake.scattering", NOMINAL_SCATTERING,
        "abep_sim/intake.py IntakeParams.scattering default, adopted as PROPOSED placeholder", "assumed")
    put("plenum.T_gas_K", d["cp"]["T_out_K"],
        "abep_sim/intake.py CompressorParams.T_out_K default (no cited source), adopted as PROPOSED placeholder",
        "assumed")
    put("plenum.backflow_frac", d["cp"]["backflow_frac"],
        "abep_sim/intake.py CompressorParams.backflow_frac default (no cited source); an UPPER BOUND on delivered flow "
        "(finding FC-01)", "assumed")
    put("compressor.mode", "size_for", "abep_sim/system.py:evaluate convention (compressor sized for the setpoint)",
        "assumed")
    for f in fe._dragcompressor_fields():
        if f in fe.COMP_SIZED_FIELDS:
            continue
        if f == "turbo_area_m2":
            put("compressor." + f, min(0.45, 0.9 * area * geom["phi"]),
                "abep_sim/system.py:evaluate convention turbo_area_m2 = min(0.45, 0.9 x intake area x phi)",
                "assumed")
        elif f == "turbo_radius_m":
            put("compressor." + f, min(0.45, math.sqrt(area / math.pi)),
                "abep_sim/system.py:evaluate convention turbo_radius_m = min(0.45, sqrt(intake area / pi))", "assumed")
        elif f == "rotor_material":
            put("compressor." + f, d["cfg"]["rotor_material"],
                "abep_sim/system.py Config.rotor_material default (no cited source), PROPOSED placeholder", "assumed")
        else:
            put("compressor." + f, d["dc"][f],
                f"abep_sim/compressor.py DragCompressor.{f} default (no cited source), PROPOSED placeholder", "assumed")
    for f in ("rpm_max", "max_turbo_rows", "max_drag_stages"):
        put("compressor.size_for." + f, d["sf"][f],
            f"abep_sim/compressor.py DragCompressor.size_for({f}) default (no cited source), PROPOSED placeholder",
            "assumed")
    for f in ("volume_m3", "wall_area_m2", "anode_orifice_K", "leak_area_m2"):
        put("chamber." + f, d["rv"][f],
            f"abep_sim/reservoir.py Reservoir.{f} default (no cited source), PROPOSED placeholder", "assumed")
    put("chamber.wall_material", d["cfg"]["reservoir_material"],
        "abep_sim/system.py Config.reservoir_material default (no cited source), PROPOSED placeholder", "assumed")
    rotor = d["cfg"]["rotor_material"]
    put("chamber.upstream_material", rotor if rotor in ("Ti6Al4V", "Al6061") else "Al2O3_anodised",
        "abep_sim/system.py:evaluate rule (rotor material kept if Ti6Al4V/Al6061, else Al2O3_anodised)", "assumed")
    put("chamber.T_K", fe.TOKEN_T_FROM_COMPRESSOR,
        "abep_sim/system.py:evaluate convention T = min(max(T_comp, 300), 500) K (finding FC-04)", "assumed")
    put("chamber.upstream_collisions", fe.TOKEN_UPSTREAM_COLLISIONS,
        "abep_sim/system.py:evaluate heuristic (no cited source; ICD G-16)", "assumed")
    put("valve.mode", "pressure_setpoint", f"{P}: architecture-neutral valve-outlet pressure setpoint", "assumed")
    put("valve.p_feed_setpoint_Pa", setpoint,
        f"{P}: setpoint ladder {list(SETPOINT_LADDER_PA)} Pa (0.05 Pa = docs/HISTORY.md v1.0 reference gas state, "
        "quoted, not adopted as a design value)", "assumed")
    doc = {"format": fe.DESIGN_INPUTS_FORMAT, "label": cid, "inputs": E}
    fe.validate_design_inputs(doc)          # lane-16 contract: raises on missing / unprovenanced / out-of-grid
    return doc


def compact(det: dict, atm: dict) -> dict:
    c = det["compressor"]
    out = {"status": det["status"], "reasons": list(det["reasons"]),
           "eta_c": det["eta_c"], "CR_passive": det["CR_passive"], "p_plenum_Pa": det["p_plenum_Pa"],
           "compressor": {"turbo_rows": c["turbo_rows"], "n_stages": c["n_stages"], "rpm": c["rpm"],
                          "sized": c["sized"], "rotor_ok": c["rotor_ok"], "CR_active": c["CR_active"],
                          "T_comp_K": c["T_comp_K"], "P_el_W": c["P_el_W"],
                          "T_clamp_active": not (300.0 <= c["T_comp_K"] <= 500.0)},
           "feed": None}
    if det["feed"] is not None:
        f = det["feed"]
        ch = det["chamber"]
        out["feed"] = {"mdot_total_kgps": f["mdot_total_kgps"], "mdot_s_kgps": f["mdot_s_kgps"],
                       "p_feed_Pa": f["p_feed_Pa"], "T_feed_K": f["T_gas_K"], "w_s": f["w_s"], "x_s": f["x_s"],
                       "O_survival": ch["O_survival"], "residence_time_s": ch["residence_time_s"],
                       "valve_area_m2": ch["anode_orifice_area_m2"], "A_eff_m2": f["A_eff_m2"]}
    return out


# --------------------------------------------------------------------------------------------------------- build
def build() -> dict:
    fe = _load_lane16()
    from abep_sim.constants import RFP, M_SPECIES
    d = code_defaults(fe)
    cases = [(a, l) for a in ALTITUDES_KM for l in LEVELS]
    atms = {}
    for a, l in cases:
        atms[case_id(a, l)] = fe.frozen_state(a, l)[0]
    atm_des = atms[case_id(*DESIGN_CASE)]

    # --- design candidates (area from the PROPOSED sizing rule at the design case)
    candidates = []
    for sid, sr in SIZING_RULES.items():
        T_N = getattr(RFP, sr["thrust_attr"]) * 1e-3
        for gid, g in GEOMETRIES.items():
            dp = drag_per_m2(atm_des, g["L_over_d"], g["phi"], NOMINAL_ACCOMMODATION, NOMINAL_OFF_AXIS_DEG,
                             NOMINAL_SCATTERING)
            area = T_N / dp["drag_N_per_m2"]
            cid = f"DC-{sid}-{gid}"
            src = (f"PROPOSED sizing rule SR-DRAG ({sr['label']}; abep_sim/constants.py RFP.{sr['thrust_attr']}) at the "
                   f"design case {case_id(*DESIGN_CASE)}: area = T / (drag per m^2 from abep_sim.intake.collection with "
                   "the frozen TPMC C_D)")
            candidates.append({"id": cid, "sizing_rule": sid, "geometry": gid, "L_over_d": g["L_over_d"],
                               "phi": g["phi"], "geometry_label": g["label"], "sizing_label": sr["label"],
                               "design_thrust_mN": T_N * 1e3, "intake_area_m2": area, "area_source": src,
                               "C_D_design_case": dp["C_D"], "eta_c_design_case": dp["eta_c"],
                               "CR_passive_design_case": dp["CR_passive"], "status": "PROPOSED",
                               "evidence_class": "assumed"})

    # --- setpoint ladder evaluation
    ladder = {}
    design_docs = {}
    for c in candidates:
        g = GEOMETRIES[c["geometry"]]
        ladder[c["id"]] = {}
        for sp in SETPOINT_LADDER_PA:
            doc = candidate_design_inputs(fe, d, c["id"], g, c["intake_area_m2"], c["area_source"], sp)
            dv = fe.validate_design_inputs(doc)
            ladder[c["id"]][f"{sp:g}"] = {cid_: compact(fe.run_chain(atms[cid_], dv, CONVENTION), atms[cid_])
                                         for cid_ in atms}

    # --- closure: common feasible setpoint band; nominal = lowest ladder value closing all nine cases
    closure = {}
    for c in candidates:
        ok_sp = [sp for sp in SETPOINT_LADDER_PA
                 if all(ladder[c["id"]][f"{sp:g}"][k]["status"] == "OK" for k in atms)]
        per_case_ok = {k: [sp for sp in SETPOINT_LADDER_PA if ladder[c["id"]][f"{sp:g}"][k]["status"] == "OK"]
                       for k in atms}
        closure[c["id"]] = {
            "status": "CLOSED" if ok_sp else "NOT_CLOSED_ON_LADDER",
            "common_feasible_setpoints_Pa": ok_sp,
            "nominal_setpoint_Pa": ok_sp[0] if ok_sp else None,
            "nominal_rule": "PROPOSED: lowest ladder setpoint that closes the chain (status OK) in all nine cases "
                            "(least compressor work; highest atomic-O survival)",
            "per_case_feasible_setpoints_Pa": per_case_ok,
            "failure_reasons": sorted({r for sp in SETPOINT_LADDER_PA for k in atms
                                       for r in ladder[c["id"]][f"{sp:g}"][k]["reasons"]}) if not ok_sp else []}

    # design-input document per candidate at its nominal setpoint (first ladder value if not closed)
    for c in candidates:
        sp = closure[c["id"]]["nominal_setpoint_Pa"] or SETPOINT_LADDER_PA[0]
        design_docs[c["id"]] = candidate_design_inputs(fe, d, c["id"], GEOMETRIES[c["geometry"]], c["intake_area_m2"],
                                                       c["area_source"], sp)

    # --- sensitivities at the nominal setpoint
    sens = {}
    for c in candidates:
        cl = closure[c["id"]]
        if cl["status"] != "CLOSED":
            continue
        sp = cl["nominal_setpoint_Pa"]
        base_doc = candidate_design_inputs(fe, d, c["id"], GEOMETRIES[c["geometry"]], c["intake_area_m2"],
                                           c["area_source"], sp)
        sens[c["id"]] = {}
        for s in SENSITIVITIES:
            doc = json.loads(json.dumps(base_doc))
            for k, v in s["override"].items():
                doc["inputs"][k] = {"value": v, "source": s["source"], "evidence_class": "assumed"}
            dv = fe.validate_design_inputs(doc)
            conv = s.get("convention", CONVENTION)
            sens[c["id"]][s["id"]] = {k: compact(fe.run_chain(atms[k], dv, conv), atms[k]) for k in atms}

    # --- valve-outlet states per closed candidate: nominal + scenario range
    from abep_sim.intake import IntakeParams, collection
    n_tpmc = int(fe._surface_meta()["n_per_point"])
    valve_outlet = {}
    for c in candidates:
        cl = closure[c["id"]]
        if cl["status"] != "CLOSED":
            continue
        sp = cl["nominal_setpoint_Pa"]
        rows = {}
        for k, atm in atms.items():
            nom = ladder[c["id"]][f"{sp:g}"][k]
            f = nom["feed"]
            scen = [("setpoint " + f"{s2:g} Pa", ladder[c["id"]][f"{s2:g}"][k]) for s2 in cl["common_feasible_setpoints_Pa"]]
            scen += [(sid, sens[c["id"]][sid][k]) for sid in sens[c["id"]]]
            okv = [(lab, r["feed"]) for lab, r in scen if r["status"] == "OK"]
            lost = [lab for lab, r in scen if r["status"] != "OK"]

            def rng(get):
                vals = [get(ff) for _, ff in okv]
                return {"min": min(vals), "max": max(vals)}
            ip = IntakeParams(area_m2=c["intake_area_m2"], accommodation=NOMINAL_ACCOMMODATION,
                              off_axis_deg=NOMINAL_OFF_AXIS_DEG, scattering=NOMINAL_SCATTERING,
                              L_over_d=c["L_over_d"], phi=c["phi"], use_tpmc=True)
            col = collection(ip, atm)
            D = col["drag_N"]
            rows[k] = {
                "altitude_km": float(k.split("_")[0][3:]), "solar_level": k.split("_")[1],
                "nominal": {"setpoint_Pa": sp, **f,
                            "compressor_P_el_W": nom["compressor"]["P_el_W"],
                            "compressor_T_comp_K": nom["compressor"]["T_comp_K"],
                            "compressor_T_clamp_active": nom["compressor"]["T_clamp_active"],
                            "compressor_stages": [nom["compressor"]["turbo_rows"], nom["compressor"]["n_stages"]],
                            "compressor_rpm": nom["compressor"]["rpm"]},
                "scenario_range": {
                    "kind": "scenario_set",
                    "members": [lab for lab, _ in okv],
                    "members_without_closure": lost,
                    "mdot_total_kgps": rng(lambda ff: ff["mdot_total_kgps"]),
                    "p_feed_Pa": rng(lambda ff: ff["p_feed_Pa"]),
                    "T_feed_K": rng(lambda ff: ff["T_feed_K"]),
                    "x_s": {s: rng(lambda ff, s=s: ff["x_s"][s]) for s in AIR},
                    "w_s": {s: rng(lambda ff, s=s: ff["w_s"][s]) for s in AIR}},
                "tpmc_sampling_rel_bound_on_mdot": 0.5 / math.sqrt(n_tpmc) / f["mdot_total_kgps"]
                                                  * atm["flux_kg_m2_s"] * c["intake_area_m2"],
                "intake_drag": {"D_int_mN": D * 1e3, "C_D": col["C_D"],
                                "D_int_over_T_min": D * 1e3 / RFP.thrust_min_mN,
                                "D_int_over_T_max": D * 1e3 / RFP.thrust_max_mN,
                                "exceeds_RFP_thrust_max": D * 1e3 > RFP.thrust_max_mN,
                                "v_req_mps": D / f["mdot_total_kgps"]},
                "ground": ground_flows(f["mdot_s_kgps"]),
            }
        valve_outlet[c["id"]] = rows

    # --- dominant sensitivities
    sensitivity_rank = []
    for cid, rows in valve_outlet.items():
        md = {k: r["nominal"]["mdot_total_kgps"] for k, r in rows.items()}
        entries = [{"axis": "altitude x solar activity (scenario)", "id": "SCEN-ATM",
                    "max_rel_change_mdot": max(md.values()) / min(md.values()) - 1.0,
                    "max_abs_change_x_O": max(r["nominal"]["x_s"]["O"] for r in rows.values())
                    - min(r["nominal"]["x_s"]["O"] for r in rows.values()),
                    "max_abs_change_T_feed_K": max(r["nominal"]["T_feed_K"] for r in rows.values())
                    - min(r["nominal"]["T_feed_K"] for r in rows.values()),
                    "cases_losing_closure": 0}]
        sp_n = closure[cid]["nominal_setpoint_Pa"]
        for sp in closure[cid]["common_feasible_setpoints_Pa"]:
            if sp == sp_n:
                continue
            entries.append(_sens_entry(f"SEN-SETPOINT-{sp:g}", "valve setpoint", rows,
                                       {k: ladder[cid][f"{sp:g}"][k] for k in rows}))
        for s in SENSITIVITIES:
            entries.append(_sens_entry(s["id"], s["axis"], rows, sens[cid][s["id"]]))
        entries.sort(key=lambda e: (-e["max_rel_change_mdot"], -e["max_abs_change_x_O"], e["id"]))
        sensitivity_rank.append({"candidate": cid, "ranked": entries})

    # design-axis effects across candidates (design case)
    k_des = case_id(*DESIGN_CASE)
    design_axis = []
    closed = [c for c in candidates if closure[c["id"]]["status"] == "CLOSED"]
    for c in closed:
        design_axis.append({"candidate": c["id"], "mdot_design_case_kgps": valve_outlet[c["id"]][k_des]["nominal"][
            "mdot_total_kgps"], "x_O_design_case": valve_outlet[c["id"]][k_des]["nominal"]["x_s"]["O"]})

    test_points, mfc = derive_test_points(candidates, closure, valve_outlet)
    return assemble(fe, d, candidates, design_docs, ladder, closure, sens, valve_outlet, sensitivity_rank,
                    design_axis, test_points, mfc, atms)


def _sens_entry(sid, axis, rows, alt_runs) -> dict:
    rel, dxo, dT, lost = 0.0, 0.0, 0.0, 0
    for k, r in rows.items():
        a = alt_runs[k]
        if a["status"] != "OK":
            lost += 1
            continue
        n = r["nominal"]
        rel = max(rel, abs(a["feed"]["mdot_total_kgps"] / n["mdot_total_kgps"] - 1.0))
        dxo = max(dxo, abs(a["feed"]["x_s"]["O"] - n["x_s"]["O"]))
        dT = max(dT, abs(a["feed"]["T_feed_K"] - n["T_feed_K"]))
    return {"axis": axis, "id": sid, "max_rel_change_mdot": rel, "max_abs_change_x_O": dxo,
            "max_abs_change_T_feed_K": dT, "cases_losing_closure": lost}


# ------------------------------------------------------------------------------------------------------ test points
def derive_test_points(candidates, closure, valve_outlet):
    k_des = case_id(*DESIGN_CASE)
    tps = {"phase1_knee_N2": [], "phase2_common_condition": [], "phase3_absolute_demonstration": []}
    union = {"mdot_min_kgps": None, "mdot_max_kgps": None, "O2_max_kgps": None, "candidates": []}
    n_levels = _knee_levels()
    for c in candidates:
        cid = c["id"]
        if closure[cid]["status"] != "CLOSED":
            continue
        rows = valve_outlet[cid]
        md = {k: r["nominal"]["mdot_total_kgps"] for k, r in rows.items()}
        k_min = min(md, key=md.get)
        k_max = max(md, key=md.get)
        m_min, m_nom, m_max = md[k_min], md[k_des], md[k_max]
        des = rows[k_des]["nominal"]
        common = {"candidate": cid, "P_feed_target_Pa": des["setpoint_Pa"],
                  "P_feed_role": "measured covariate at the valve-outlet plane (lane 25 Sec. 4); matched by pressure "
                                 "control only if the owner decides so (DI-1.9)",
                  "T_feed_flight_K": des["T_feed_K"],
                  "T_feed_ground": "TBD - requires owner decision DI-1.10 (feed-gas temperature conditioning)"}
        # Phase 1: N2 knee ladder (lane 25 knee scan: equally spaced from mdot_nom down to mdot_min, then back up)
        for i in range(n_levels):
            m = m_nom - (m_nom - m_min) * i / (n_levels - 1)
            tps["phase1_knee_N2"].append({
                "id": f"TP1-{cid}-L{i + 1}", "phase": 1, "gas": "N2", "basis": "mass-equivalent (DI-1.8 PROPOSED)",
                "mdot_N2_kgps": m, "mdot_N2_mgps": m * 1e6, "sccm_N2": m / _M("N2") / sccm_molecules_per_s(),
                "trace": {"level": i + 1, "of": n_levels, "from": {"mdot_nom": k_des, "mdot_min": k_min},
                          "rule": "lane-25 knee scan (T-KNEE-LEVELS equally spaced flows, nom -> min, then back up)"},
                **common})
        tps["phase1_knee_N2"].append({
            "id": f"TP1-{cid}-EXT", "phase": 1, "gas": "N2", "basis": "mass-equivalent (DI-1.8 PROPOSED)",
            "mdot_N2_kgps": m_max, "mdot_N2_mgps": m_max * 1e6, "sccm_N2": m_max / _M("N2") / sccm_molecules_per_s(),
            "trace": {"level": "upper extension", "from": {"mdot_max": k_max},
                      "rule": "PROPOSED optional point: upper edge of the candidate's feed envelope (not in the lane-25 "
                              "minimum)"}, **common})
        # Phase 2: OP1/OP2/OP3 on N2, OP5 air surrogate at the knee (lane 25 operating points)
        gdes = rows[k_des]["ground"]["air_surrogate_N2_O2"]
        for op, m, src in (("OP1", m_min, k_min), ("OP2", None, "Phase-1 knee"), ("OP3", m_nom, k_des)):
            tps["phase2_common_condition"].append({
                "id": f"TP2-{cid}-{op}", "phase": 2, "operating_point": op, "gas": "N2",
                "basis": "mass-equivalent (DI-1.8 PROPOSED)",
                "mdot_N2_kgps": m, "mdot_N2_mgps": None if m is None else m * 1e6,
                "sccm_N2": None if m is None else m / _M("N2") / sccm_molecules_per_s(),
                "value_status": "PROPOSED" if m is not None else "TBD - requires the measured Phase-1 knee "
                                                                  "(lane 25 T-OP2-FALLBACK)",
                "trace": {"from": src}, "arms": list(ARCHITECTURES), **common})
        tps["phase2_common_condition"].append({
            "id": f"TP2-{cid}-OP5", "phase": 2, "operating_point": "OP5", "gas": "N2+O2 air surrogate",
            "basis": "O supplied as O2 at equal oxygen-element mass (DI-1.7 PROPOSED)",
            "mdot_total_kgps": None, "w_O2": gdes["w_O2"], "w_N2": gdes["w_N2"],
            "value_status": "TBD - total flow = the measured Phase-1 knee; composition PROPOSED from the design case",
            "trace": {"composition_from": k_des}, "arms": list(ARCHITECTURES), **common})
        # Phase 3: every case, N2-only then air surrogate
        for k, r in rows.items():
            g = r["ground"]
            n = r["nominal"]
            base = {"candidate": cid, "P_feed_target_Pa": n["setpoint_Pa"], "T_feed_flight_K": n["T_feed_K"],
                    "T_feed_ground": common["T_feed_ground"], "P_feed_role": common["P_feed_role"],
                    "trace": {"case": k, "altitude_km": r["altitude_km"], "solar_level": r["solar_level"]},
                    "flight_x_s": n["x_s"], "flight_w_s": n["w_s"],
                    "mdot_scenario_range_kgps": r["scenario_range"]["mdot_total_kgps"]}
            tps["phase3_absolute_demonstration"].append({
                "id": f"TP3-{cid}-{k}-N2", "phase": 3, "gas": "N2", "basis": "mass-equivalent (DI-1.8 PROPOSED)",
                "mdot_N2_kgps": g["N2_only_mass_equivalent"]["mdot_N2_kgps"],
                "sccm_N2": g["N2_only_mass_equivalent"]["sccm_N2"], **base})
            a = g["air_surrogate_N2_O2"]
            tps["phase3_absolute_demonstration"].append({
                "id": f"TP3-{cid}-{k}-AIR", "phase": 3, "gas": "N2+O2 air surrogate",
                "basis": "O supplied as O2 at equal oxygen-element mass (DI-1.7 PROPOSED)",
                "mdot_N2_kgps": a["mdot_N2_kgps"], "mdot_O2_kgps": a["mdot_O2_kgps"], "sccm_N2": a["sccm_N2"],
                "sccm_O2": a["sccm_O2"], "w_O2": a["w_O2"],
                "particle_flow_ratio_ground_over_flight": a["particle_flow_ratio_ground_over_flight"], **base})
        lo = min(r["scenario_range"]["mdot_total_kgps"]["min"] for r in rows.values())
        hi = max(r["scenario_range"]["mdot_total_kgps"]["max"] for r in rows.values())
        o2 = max(r["ground"]["air_surrogate_N2_O2"]["mdot_O2_kgps"] for r in rows.values())
        union["mdot_min_kgps"] = lo if union["mdot_min_kgps"] is None else min(union["mdot_min_kgps"], lo)
        union["mdot_max_kgps"] = hi if union["mdot_max_kgps"] is None else max(union["mdot_max_kgps"], hi)
        union["O2_max_kgps"] = o2 if union["O2_max_kgps"] is None else max(union["O2_max_kgps"], o2)
        union["candidates"].append(cid)
    if union["candidates"]:
        from abep_sim.constants import RFP
        acc = RFP.mission_hours / RFP.ignition_hours
        union.update({
            "sccm_N2_min": union["mdot_min_kgps"] / _M("N2") / sccm_molecules_per_s(),
            "sccm_N2_max": union["mdot_max_kgps"] / _M("N2") / sccm_molecules_per_s(),
            "sccm_O2_max": union["O2_max_kgps"] / _M("O2") / sccm_molecules_per_s(),
            "accumulation_factor_upper": acc,
            "mdot_max_with_accumulation_kgps": union["mdot_max_kgps"] * acc,
            "accumulation_note": "RFP mission 26,000 h / firing > 15,000 h gives an upper factor if all collected "
                                 "gas were stored and fired in the minimum firing time; requires a storage model not "
                                 "in the repository (finding FC-08); PROPOSED as MFC headroom only",
            "note": "min/max over every closed candidate's nine cases and scenario ranges: an instrumentation range "
                    "requirement input for W4 (MFC full scale and resolution), not a test point"})
    return tps, union


def _M(s):
    from abep_sim.constants import M_SPECIES
    return M_SPECIES[s]


def _knee_levels() -> int:
    p = REPO / LANE25_DRAFT_REL
    if not p.exists():
        return KNEE_LEVELS_FALLBACK
    for t in json.loads(p.read_text()).get("thresholds", []):
        if t.get("id") == "T-KNEE-LEVELS":
            return int(t["value"])
    raise FeedClosureError("T-KNEE-LEVELS not found in the lane-25 draft")


# ------------------------------------------------------------------------------------------------------ assembly
def design_input_inventory(fe, d, candidates, design_docs) -> list[dict]:
    inv = []
    cat = fe.design_input_catalog()
    first = design_docs[candidates[0]["id"]]["inputs"]
    varying = {"intake.area_m2", "intake.L_over_d", "compressor.turbo_area_m2", "compressor.turbo_radius_m",
               "valve.p_feed_setpoint_Pa"}
    lit = {"intake.area_m2": ["LIT-01"], "intake.accommodation": ["LIT-02", "LIT-03"],
           "intake.L_over_d": ["LIT-02"], "intake.off_axis_deg": ["LIT-03"]}
    for e in cat:
        n = e["name"]
        used = first.get(n)
        entry = {"name": n, "unit": e["unit"], "consumer": e["consumer"], "required_when": e["required_when"]}
        if used is None:
            entry.update({"value": None, "status": "NOT_USED_IN_SELECTED_MODES", "source": None,
                          "evidence_class": None})
        elif n in varying:
            entry.update({"value": "per candidate (see candidates / design_input_documents)",
                          "status": "PROPOSED", "source": used["source"], "evidence_class": used["evidence_class"]})
        else:
            entry.update({"value": used["value"], "status": "PROPOSED", "source": used["source"],
                          "evidence_class": used["evidence_class"]})
        entry["published_comparables"] = lit.get(n, [])
        inv.append(entry)
    extra = [
        ("sizing.design_case", "-", f"{case_id(*DESIGN_CASE)}", "PROPOSED",
         "PROPOSED mid-envelope design case for the area sizing rule (owner decision DI-1.1)", "assumed"),
        ("sizing.rule", "-", "SR-DRAG: intake-only drag at the design case = RFP thrust level (12 or 25 mN)",
         "PROPOSED", "abep_sim/constants.py RFP thrust_min_mN / thrust_max_mN; rule PROPOSED (DI-1.1)", "assumed"),
        ("sizing.body_drag_share", "-", None, "TBD",
         "TBD - requires the spacecraft frontal area and C_D (not in this chain); a body-drag share f reduces the "
         "admissible intake area and the delivered flow by (1 - f)", None),
        ("operation.duty_cycle_and_storage", "-", None, "TBD",
         "TBD - requires the firing schedule and a gas-storage model (none in the repository; reservoir.py is a "
         "low-pressure lumped buffer); RFP ratio 26,000 h / 15,000 h bounds accumulation (FC-08)", None),
        ("intake.filter", "-", None, "TBD",
         "TBD - requires a filter model (ICD G-01); the frozen TPMC surface has no filter", None),
        ("xe_path.all", "-", None, "TBD",
         "TBD - requires a Xe storage / regulator / valve model (ICD G-12); cathode Xe flow belongs to C-1 (lane 19)",
         None),
        ("ground.equivalence_basis", "-", "mass-equivalent (particle-equivalent carried)", "PROPOSED",
         "PROPOSED (DI-1.8): N2 test flow equal to the flight valve-outlet mass flow", "assumed"),
        ("ground.air_surrogate", "-", "N2 + O2, O supplied as O2 at equal oxygen-element mass", "PROPOSED",
         "PROPOSED (DI-1.7); same convention as lane 25 Sec. 4 composition axis", "assumed"),
        ("ground.sccm_reference", "-", f"{SCCM_T0_K} K, {SCCM_P0_PA} Pa", "PROPOSED",
         "definition used for the sccm conversion; every MFC's own standard conditions must be checked (verify)",
         "assumed"),
        ("ground.T_feed_conditioning", "K", None, "TBD", "TBD - owner decision DI-1.10", None),
    ]
    for n, u, v, st, src, ev in extra:
        inv.append({"name": n, "unit": u, "consumer": "this document (test-point derivation)", "required_when": "always",
                    "value": v, "status": st, "source": src, "evidence_class": ev, "published_comparables": []})
    return inv


def owner_decisions() -> list[dict]:
    return [
        {"id": "DI-1.1", "question": "Area sizing rule and design case", "options": [
            "SR-DRAG at 200 km mean with 12 mN (S12) or 25 mN (S25) [PROPOSED candidates]",
            "another design case (e.g. 180 km high, the highest drag state) or a body-drag share",
            "a Vyovrinda intake area from the mass/drag budget (supplied with provenance)"],
         "recommendation": "PROPOSED: carry S12 and S25 as the bracketing pair until a spacecraft drag budget exists"},
        {"id": "DI-1.2", "question": "Intake geometry (L/d, phi) and whether a TPMC surface beyond the frozen grid "
                                     "(e.g. specular designs) is authorised (CLAUDE.md rule 1 rebuild)",
         "options": ["G10", "G20", "G03 (not closed on the ladder)", "new geometry + surface rebuild"],
         "recommendation": "PROPOSED: G10 and G20 as the closed pair; G03 only with a compressor concept that swallows "
                           "its flow (FC-03)"},
        {"id": "DI-1.3", "question": "Surface state / accommodation for the design case (diffuse 1.0 nominal)",
         "options": ["1.0 (diffuse, conservative)", "0.8 (code prior mode)", "measured coupon data"],
         "recommendation": "PROPOSED: 1.0 nominal, 0.8 and 0.5 as sensitivities"},
        {"id": "DI-1.4", "question": "Compressor concept and parameters (all DragCompressor fields are code "
                                     "defaults without a cited source)",
         "options": ["size_for with code defaults (PROPOSED placeholder)", "a sourced compressor design",
                     "passive (no active compressor) intake"],
         "recommendation": "TBD - requires a sourced compressor design; code defaults are placeholders"},
        {"id": "DI-1.5", "question": "Buffer (atmospheric gas chamber) volume, wall material and temperature policy",
         "options": ["Reservoir code defaults + Config wall material (PROPOSED placeholder)", "sourced design"],
         "recommendation": "TBD - the wall material drives atomic-O survival at the valve outlet (see sensitivities)"},
        {"id": "DI-1.6", "question": "Valve-outlet pressure setpoint P_feed (architecture-neutral)",
         "options": [f"ladder {list(SETPOINT_LADDER_PA)} Pa; nominal = lowest value closing all nine cases",
                     "a setpoint derived from the H-1 anode injector conductance (W3)"],
         "recommendation": "PROPOSED: nominal per candidate from the ladder rule; P_feed recorded as a covariate"},
        {"id": "DI-1.7", "question": "Air surrogate definition (atomic O cannot be supplied from bottles)",
         "options": ["S-O2E: N2 + O2 with O as O2 at equal O-element mass [PROPOSED]",
                     "S-O2M: N2 + O2 at equal molar O fraction", "S-AR: argon substitution for O (LIT-07)",
                     "an atomic-O source upstream of H-1 (confounds the paired pre-ionizer comparison)"],
         "recommendation": "PROPOSED: S-O2E (matches lane 25 Sec. 4); atomic-O effect left to W7 chemistry"},
        {"id": "DI-1.8", "question": "Ground equivalence basis for N2 test flows",
         "options": ["mass-equivalent [PROPOSED]", "particle-equivalent (carried alongside)"],
         "recommendation": "PROPOSED: mass-equivalent; report both"},
        {"id": "DI-1.9", "question": "Is P_feed controlled to the flight value or only measured (lane 25: covariate)?",
         "options": ["measured covariate (lane 25)", "controlled with a pressure controller / restrictor"],
         "recommendation": "PROPOSED: measured covariate; mismatch flagged as an applicability limit"},
        {"id": "DI-1.10", "question": "Feed-gas temperature conditioning on the ground (flight T_feed 300-500 K by "
                                      "the chain's clamp convention)",
         "options": ["room temperature, recorded", "heated feed line to the flight T_feed"],
         "recommendation": "TBD - owner decision; the chain's T_feed is a clamp convention (FC-04), not a design value"},
        {"id": "DI-1.11", "question": "Which candidate(s) define the frozen DI-1 test-point set",
         "options": ["the union of closed candidates (MFC range)", "one candidate after DI-1.1..1.6"],
         "recommendation": "PROPOSED: freeze the union MFC range now (hardware lead time); freeze point values after "
                           "DI-1.1..1.6"},
        {"id": "DI-1.12", "question": "Backflow / plenum-pressure inconsistency (FC-01): accept the delivered flow "
                                      "as an upper bound, or authorise a chain model change (goldens may move)",
         "options": ["upper bound, documented", "model change via the normal process (HISTORY entry)"],
         "recommendation": "PROPOSED: upper bound for LOCK-1; the Phase-1 ladder reaches down to the envelope minimum"},
    ]


def findings(candidates, closure, valve_outlet, sens) -> list[dict]:
    closed = [c["id"] for c in candidates if closure[c["id"]]["status"] == "CLOSED"]
    not_closed = [c["id"] for c in candidates if closure[c["id"]]["status"] != "CLOSED"]
    clamp = sum(1 for cid in valve_outlet for r in valve_outlet[cid].values() if r["nominal"]["compressor_T_clamp_active"])
    clamp_all = sum(1 for cid in sens for runs in sens[cid].values() for r in runs.values()
                    if r["status"] == "OK" and r["compressor"]["T_clamp_active"])
    n_all = sum(1 for cid in sens for runs in sens[cid].values() for r in runs.values() if r["status"] == "OK")
    over = sorted({(cid, k) for cid in valve_outlet for k, r in valve_outlet[cid].items()
                   if r["intake_drag"]["exceeds_RFP_thrust_max"]})
    xo = [r["nominal"]["x_s"]["O"] for cid in valve_outlet for r in valve_outlet[cid].values()]
    xo_scen = [r["scenario_range"]["x_s"]["O"] for cid in valve_outlet for r in valve_outlet[cid].values()]
    return [
        {"id": "FC-01", "where": "abep_sim/intake.py:compress; abep_sim/intake_tpmc.py CR_passive",
         "finding": "the chain delivers the full forward-transmitted flow eta_c x rhoV x A x (1 - backflow_frac) while "
                    "feeding the compressor at the passive plenum pressure p_passive; p_passive is, by the TPMC flux "
                    "balance (CR_passive = eta_c V / (c_bar/4 phi K_back)), the plenum state at which backflow equals "
                    "inflow (zero net collection). backflow_frac is an independent input (default 0), so the delivered "
                    "flow is an UPPER BOUND; with b = p_plenum/p_passive the net flow scales by (1 - b)",
         "evidence_class": "inferred", "handling": "stated, not fixed (module change outside this lane; DI-1.12)"},
        {"id": "FC-02", "where": "abep_sim/intake_tpmc.py eta_c definition",
         "finding": "the frozen TPMC eta_c is the forward transmission into the plenum (eta_c = phi x eta_open x "
                    "cos theta); for fully diffuse walls it reaches 0.74 at L/d 3 and 0.45 at L/d 10, whereas "
                    "published diffuse intake designs report eta_c < 0.46 (LIT-03) and 0.28-0.45 (LIT-02) with "
                    "backflow included; consistent with FC-01, not a validation of either",
         "evidence_class": "inferred", "handling": "cross-check only"},
        {"id": "FC-03", "where": "abep_sim/compressor.py DragCompressor (Gaede characteristic)",
         "finding": "closure requires compressor pumping speed well above the plenum volumetric flow Q/p ~ eta_c V A / "
                    "CR_passive; short-channel intakes (high eta_c, low CR_passive) and large areas at code-default "
                    f"compressor parameters do not close on the setpoint ladder: {not_closed or 'none'}",
         "evidence_class": "model-derived", "handling": "reported per candidate (closure.failure_reasons)"},
        {"id": "FC-04", "where": "abep_sim/system.py:evaluate chamber temperature convention",
         "finding": f"T_feed = min(max(T_comp, 300), 500) K; the clamp is active in {clamp} nominal closed-candidate "
                    f"cases and in {clamp_all} of {n_all} closed sensitivity runs; there T_feed is a convention, not a "
                    "thermal result",
         "evidence_class": "model-derived", "handling": "flag compressor_T_clamp_active per case"},
        {"id": "FC-05", "where": "abep_sim/reservoir.py O recombination; compressor stage count and temperature",
         "finding": "the valve-outlet atomic-O mole fraction is a design output, not an atmosphere property: nominal "
                    f"x_O {min(xo):.3g}-{max(xo):.3g} across closed candidates and cases, scenario range "
                    f"{min(v['min'] for v in xo_scen):.3g}-{max(v['max'] for v in xo_scen):.3g} (setpoint, wall "
                    "material, temperature)",
         "evidence_class": "model-derived", "handling": "air-surrogate composition taken per case; MD section 7"},
        {"id": "FC-06", "where": "Hall-free momentum balance (intake-only drag)",
         "finding": "with area sized at 200 km mean, the intake-only drag exceeds the RFP maximum thrust (25 mN) at "
                    f"{len(over)} closed candidate-cases: " + ", ".join(f"{a}/{b}" for a, b in over)
                    + ". If full drag compensation is required, it is impossible at those cases within the RFP thrust band "
                      "whatever the thruster (body drag would add). Not an elimination: a sizing/design-case consequence for DI-1.1",
         "evidence_class": "model-derived", "handling": "reported per case (intake_drag.exceeds_RFP_thrust_max)"},
        {"id": "FC-07", "where": "abep_sim/intake.py:_tpmc_surface (lane 16 FE-08)",
         "finding": "the frozen TPMC surface was built at 200 km / F10.7 150; its speed-ratio dependence at the other "
                    "eight cases is not characterised (lane 16 computed -17 %..+15 % in sqrt(T/m))",
         "evidence_class": "model-derived", "handling": "not propagated; TBD - requires TPMC surfaces at other states"},
        {"id": "FC-08", "where": "chain scope (steady state)",
         "finding": "the chain is steady-state continuous collection = continuous firing; accumulate-and-fire operation "
                    "(RFP firing > 15,000 h of 26,000 h) is not modelled and would raise the firing flow by up to "
                    "26,000/15,000",
         "evidence_class": "assumed", "handling": "MFC headroom only (union.accumulation_factor_upper)"},
        {"id": "FC-09", "where": "closed candidates",
         "finding": f"closed on the PROPOSED ladder: {closed}",
         "evidence_class": "model-derived", "handling": "test points derived only from closed candidates"},
    ]


def atomic_oxygen_section(valve_outlet) -> dict:
    return {
        "can_atomic_O_be_supplied_from_bottles": False,
        "why": "atomic O is not storable as a bottled gas: it recombines to O2 on walls and in the gas phase; a "
               "ground feed of atomic O needs an on-line dissociation source (inferred; standard AO-facility practice "
               "uses discharge or laser sources: verify)",
        "surrogates": [
            {"id": "S-N2", "definition": "pure N2 at the flight mass flow", "use": "Phase 1 knee and Phase 2 OP1-OP3",
             "limitation": "no oxygen chemistry at all"},
            {"id": "S-O2E", "definition": "N2 + O2, O supplied as O2 at equal oxygen-element mass "
                                          "(w_O2,ground = w_O + w_O2 at the valve outlet)",
             "use": "PROPOSED air surrogate for OP5 and Phase 3", "status": "PROPOSED",
             "limitation": "fewer particles than the flight feed (particle_flow_ratio_ground_over_flight < 1 per test "
                           "point); every surrogate O atom arrives bound in O2, so the discharge must dissociate it "
                           "(O2 bond energy, abep_sim/system.py diss_sink uses 5.12 eV per O2: verify) and O2 "
                           "ionization/attachment channels differ from O; the effect on T and on R_arch is unknown "
                           "and not bounded here"},
            {"id": "S-O2M", "definition": "N2 + O2 at equal molar oxygen fraction", "use": "not proposed",
             "limitation": "changes the element mass flow; conflicts with the mass-equivalent basis"},
            {"id": "S-AR", "definition": "argon replacing atomic O (LIT-07)", "use": "not proposed",
             "limitation": "argon has no oxygen chemistry or wall oxidation; mass 40 vs 16 amu (inferred)"},
            {"id": "S-AO-SOURCE", "definition": "an atomic-O source upstream of H-1", "use": "not proposed",
             "limitation": "adds a dissociating power input in the feed path, which the paired pre-ionizer "
                           "comparison (HW-0/HW-RF/HW-ECR) must not contain; would need its own ledger term"}],
        "consequence": "Phase 3 absolute thrust on S-O2E is an O2-surrogate demonstration. It does not demonstrate "
                       "thrust on the flight atomic-O fraction; the gap is carried as a limitation to Milestone B "
                       "(W7 O/O2 chemistry and an admitted closure are needed to transfer it)",
        "valve_outlet_x_O_ranges": {cid: {k: r["scenario_range"]["x_s"]["O"] for k, r in rows.items()}
                                    for cid, rows in valve_outlet.items()},
    }


def milestones() -> dict:
    return {
        "supports": ["A"],
        "A": "Gives LOCK-1 (W2) explicit, traceable PROPOSED values for the lane-25 flow levels (m_dot_min, m_dot_nom, "
             "OP5 composition) and the MFC range (W4), conditional on the listed design candidates, so a conditional "
             "selection 'architecture X is baseline provided ...' can be written against sourced feed conditions. "
             "It needs no Physics Baseline 1.0 and contains no Hall prediction.",
        "to_reach_B": [
            "owner decisions DI-1.1..DI-1.12 and a sourced Vyovrinda intake/compressor/buffer design replacing the "
            "PROPOSED placeholders (every code default here is 'assumed')",
            "resolution of FC-01 (net collection with backflow) through a controlled model change",
            "TPMC surfaces at the other atmospheric states (FC-07) and an NRLMSIS error characterisation",
            "an admitted Hall transport closure (physics track) to turn the test-point flows into credible thrust "
            "envelopes; W7 O/O2 chemistry for the atomic-O gap",
            "measured Phase-1/2 results at these test points"],
        "to_reach_C": [
            "storage / duty-cycle model (FC-08), Xe path model (ICD G-12), filter model (ICD G-01)",
            "compressor mass, power and heat integrated into the PDR budgets (bus_power_boundary_v1 compressor term)",
            "Phase-3 absolute demonstration across the frozen test-point set"],
    }


def assemble(fe, d, candidates, design_docs, ladder, closure, sens, valve_outlet, sensitivity_rank, design_axis,
             test_points, mfc, atms) -> dict:
    inputs = ["abep_sim/data/atmosphere_msis21_v1.csv", "abep_sim/data/atmosphere_msis21_v1.json",
              "abep_sim/data/intake_surface_v1.csv", "abep_sim/data/intake_surface_v1.json", LANE16_SCRIPT_REL,
              "abep_sim/atmosphere.py", "abep_sim/intake.py", "abep_sim/intake_tpmc.py", "abep_sim/compressor.py",
              "abep_sim/reservoir.py", "abep_sim/materials.py", "abep_sim/constants.py", "abep_sim/system.py",
              DECISION_REL, LANE25_DRAFT_REL]
    return {
        "schema": SCHEMA_ID, "version": VERSION, "status": "DRAFT for owner review",
        "follow_on": "fo_feed_state_closure", "trigger": "T_PIVOT_FEED_STATE_CLOSURE",
        "owner_disposition": {"id": "od_hardware_pivot", "file": DECISION_REL, "workstream": "W1_feed_state_closure"},
        "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "architectures": list(ARCHITECTURES),
        "architecture_independence": "no value depends on the architecture id: the feed state is defined at the valve "
                                     "outlet (ICD IF-A5), upstream of any pre-ionizer, and is identical for "
                                     "hall_only / rf_hall / ecr_hall",
        "closure_independence": "no Hall transport closure, ensemble member, screening candidate or P5 calibration-"
                                "nuisance variable enters any value; Hall modules are not imported",
        "milestones": milestones(),
        "interfaces": {"thruster_boundary": "IF-A5 (schemas/interfaces/upstream_icd_v1.json)",
                       "feed_envelope": "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json (lane 16)",
                       "operating_points": f"{LANE25_DRAFT_REL} (lane 25 knee scan and OP1-OP5)",
                       "cross_references_planned": ["fo_lock1_decision_brief (W2)", "fo_hardware_definition (W3)",
                                                    "fo_instrumentation_definition (W4)",
                                                    "fo_hall_validation_prereg_draft (W5)",
                                                    "fo_o_o2_chemistry_v0 (W7)"]},
        "provenance": {"input_files": [{"path": p, "sha256": sha256_file(p)} for p in inputs],
                       "chain": f"{LANE16_SCRIPT_REL}:run_chain (convention '{CONVENTION}'), frozen_state, "
                                "validate_design_inputs; abep_sim.intake.collection (drag, sizing)"},
        "references": REFERENCES,
        "published_comparables": list(COMPARABLES),
        "design_input_inventory": design_input_inventory(fe, d, candidates, design_docs),
        "design_axes": {"design_case": case_id(*DESIGN_CASE), "sizing_rules": SIZING_RULES,
                        "geometries": GEOMETRIES, "setpoint_ladder_Pa": list(SETPOINT_LADDER_PA),
                        "sensitivities": [dict(s) for s in SENSITIVITIES], "status": "PROPOSED"},
        "candidates": candidates,
        "design_input_documents": design_docs,
        "ladder_runs": {c: {sp: {k: slim(r) for k, r in runs.items()} for sp, runs in v.items()}
                        for c, v in ladder.items()},
        "closure": closure,
        "sensitivity_runs": {c: {sid: {k: slim(r) for k, r in runs.items()} for sid, runs in v.items()}
                             for c, v in sens.items()},
        "valve_outlet": valve_outlet,
        "sensitivity_ranking": sensitivity_rank,
        "design_axis_effects_at_design_case": design_axis,
        "test_points": test_points,
        "mfc_range_requirement": mfc,
        "atomic_oxygen": atomic_oxygen_section(valve_outlet),
        "findings": findings(candidates, closure, valve_outlet, sens),
        "owner_decisions_DI1": owner_decisions(),
    }


def slim(r: dict) -> dict:
    """Run record as stored in the JSON (the full nominal state is in `valve_outlet`)."""
    c = r["compressor"]
    out = {"status": r["status"], "reasons": r["reasons"],
           "compressor": {k: c[k] for k in ("turbo_rows", "n_stages", "rpm", "P_el_W", "T_comp_K")}}
    f = r["feed"]
    if f is not None:
        out["feed"] = {"mdot_total_kgps": f["mdot_total_kgps"], "p_feed_Pa": f["p_feed_Pa"], "T_feed_K": f["T_feed_K"],
                       "x_s": f["x_s"], "O_survival": f["O_survival"]}
    else:
        out["feed"] = None
    return out


# ------------------------------------------------------------------------------------------------------ rounding
def rnd(x):
    if isinstance(x, bool) or x is None or isinstance(x, (str, int)):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            raise FeedClosureError(f"non-finite value {x!r} reached the output")
        return 0.0 if x == 0.0 else float(f"{x:.12g}")
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v) for v in x]
    return x


# ------------------------------------------------------------------------------------------------------ markdown
def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# W1 feed-state closure v1 — valve-outlet test points for the common-hardware experiment")
    a("")
    a(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}`. Do not edit by hand; rerun the script (`--check` verifies).")
    a("")
    a("| | |\n|---|---|")
    a(f"| machine-readable | [`{JSON_NAME}`]({JSON_NAME}), schema [`{SCHEMA_NAME}`]({SCHEMA_NAME}) |")
    a(f"| status | **{doc['status']}** (version {doc['version']}); every value not in the RFP is PROPOSED |")
    a(f"| lane | `{doc['follow_on']}` (trigger `{doc['trigger']}`, owner disposition `od_hardware_pivot`, W1) |")
    a("| milestone | supports **A**; what B and C need is in section 10 |")
    a("| architectures | `hall_only`, `rf_hall`, `ecr_hall`: identical feed record (valve outlet, ICD IF-A5) |")
    a("| test | `tests/test_feed_state_closure.py` |")
    a("")
    a("**What it is.** The frozen-atmosphere → intake → compressor → buffer → valve chain of the repository evaluated "
      "for six explicit, labelled design candidates, giving valve-outlet states {ṁ_s, P_feed, T_feed, x_s} with "
      "scenario ranges and dominant sensitivities, and a PROPOSED ground test-point set (Phase 1 N₂ knee, Phase 2 "
      "common condition, Phase 3 absolute demonstration) traceable to candidate and altitude/solar case.")
    a("")
    a("**What it is not.** Not a design baseline (every design input is `assumed`/PROPOSED or TBD), not a Hall "
      "prediction, not an architecture ranking, not a model change. No module is modified; the lane-16 chain "
      "(`scripts/architecture/build_feed_envelope.py:run_chain`) is used unchanged. No Hall closure, screening "
      "candidate or P5 calibration nuisance enters any value.")
    a("")
    # 1 candidates
    a("## 1. Design candidates (PROPOSED)")
    a("")
    a(f"Area sizing rule **SR-DRAG** (PROPOSED): the intake-only free-molecular drag at the design case "
      f"`{doc['design_axes']['design_case']}` equals an RFP thrust level (12 or 25 mN, `abep_sim/constants.py` RFP), "
      "with C_D from the frozen TPMC surface. Common nominal inputs: Maxwell scattering, accommodation 1.0 (fully "
      "diffuse), 0° pointing, compressor `size_for` with code-default parameters and the `system.evaluate` turbo "
      "area/radius convention (CFRP rotor), buffer = `Reservoir` defaults with the `system.Config` wall material, "
      "valve in pressure-setpoint mode on the ladder "
      f"{doc['design_axes']['setpoint_ladder_Pa']} Pa. Each input's source and evidence class is in "
      "`design_input_documents` (lane-16 `feed_design_inputs_v1` format, validated by the lane-16 contract).")
    a("")
    a("| candidate | sizing | L/d | φ | area [m²] | C_D | η_c (design case) | CR_passive | closure | nominal P_feed [Pa] | common feasible P_feed [Pa] |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in doc["candidates"]:
        cl = doc["closure"][c["id"]]
        a(f"| {c['id']} | {c['sizing_rule']} ({fmt(c['design_thrust_mN'])} mN) | {fmt(c['L_over_d'])} | "
          f"{fmt(c['phi'])} | {fmt(c['intake_area_m2'])} | {fmt(c['C_D_design_case'])} | "
          f"{fmt(c['eta_c_design_case'])} | {fmt(c['CR_passive_design_case'])} | **{cl['status']}** | "
          f"{fmt(cl['nominal_setpoint_Pa'])} | {', '.join(fmt(v) for v in cl['common_feasible_setpoints_Pa']) or '—'} |")
    a("")
    nc = [c["id"] for c in doc["candidates"] if doc["closure"][c["id"]]["status"] != "CLOSED"]
    if nc:
        a("Candidates not closed on the ladder (no setpoint closes all nine cases), with the chain's reasons:")
        a("")
        for cid in nc:
            a(f"- `{cid}`: " + "; ".join(doc["closure"][cid]["failure_reasons"]))
        a("")
    # 2 inventory
    a("## 2. Design-input inventory")
    a("")
    a("Every input the chain needs (lane-16 contract) plus the inputs of the test-point derivation. `varies` = per "
      "candidate. None has a sourced Vyovrinda design value today.")
    a("")
    a("| input | unit | value used | status | evidence class | source | comparables |")
    a("|---|---|---|---|---|---|---|")
    for e in doc["design_input_inventory"]:
        v = e["value"]
        vs = "varies" if isinstance(v, str) and v.startswith("per candidate") else fmt(v) if not isinstance(v, str) else v
        a(f"| `{e['name']}` | {e['unit'] or '-'} | {vs} | {e['status']} | {e['evidence_class'] or '—'} | "
          f"{e['source'] or '—'} | {', '.join(e['published_comparables']) or '—'} |")
    a("")
    # 3 literature
    a("## 3. Published comparables (context only; never a performance source)")
    a("")
    a("| id | source | where | statement | used for |")
    a("|---|---|---|---|---|")
    for c in doc["published_comparables"]:
        a(f"| {c['id']} | {c['ref']} | {c['where']} | {c['statement']} | {c['relevance']} |")
    a("")
    for rid, r in doc["references"].items():
        a(f"- **{rid}**: {r['citation']}. DOI {r['doi']}. Accessed: {r['accessed']}. {r['note']}.")
    a("")
    # 4 valve outlet
    a("## 4. Valve-outlet states (ICD IF-A5) per closed candidate")
    a("")
    a("Nominal = candidate at its nominal setpoint; range = scenario set over the common feasible setpoints and the "
      "one-at-a-time sensitivity variants that close (not a probability interval). ṁ is an upper bound (FC-01).")
    a("")
    for cid, rows in doc["valve_outlet"].items():
        a(f"### {cid}")
        a("")
        a("| case | ṁ [mg/s] (range) | P_feed [Pa] (range) | T_feed [K] (range) | x_O (range) | x_N2 | x_O2 | P_el,comp [W] | T clamp | D_int [mN] | v_req [km/s] |")
        a("|---|---|---|---|---|---|---|---|---|---|---|")
        for k, r in rows.items():
            n, s = r["nominal"], r["scenario_range"]
            a(f"| {k} | {fmt(n['mdot_total_kgps'] * 1e6)} ({fmt(s['mdot_total_kgps']['min'] * 1e6)}–"
              f"{fmt(s['mdot_total_kgps']['max'] * 1e6)}) | {fmt(n['p_feed_Pa'])} ({fmt(s['p_feed_Pa']['min'])}–"
              f"{fmt(s['p_feed_Pa']['max'])}) | {fmt(n['T_feed_K'])} ({fmt(s['T_feed_K']['min'])}–"
              f"{fmt(s['T_feed_K']['max'])}) | {fmt(n['x_s']['O'], 3)} ({fmt(s['x_s']['O']['min'], 3)}–"
              f"{fmt(s['x_s']['O']['max'], 3)}) | {fmt(n['x_s']['N2'], 3)} | {fmt(n['x_s']['O2'], 3)} | "
              f"{fmt(n['compressor_P_el_W'], 3)} | {'yes' if n['compressor_T_clamp_active'] else 'no'} | "
              f"{fmt(r['intake_drag']['D_int_mN'], 3)}{' **>25**' if r['intake_drag']['exceeds_RFP_thrust_max'] else ''} | "
              f"{fmt(r['intake_drag']['v_req_mps'] / 1e3, 3)} |")
        lost = sorted({m for r in rows.values() for m in r["scenario_range"]["members_without_closure"]})
        if lost:
            a("")
            a("Scenario members that lose closure in at least one case: " + ", ".join(f"`{m}`" for m in lost) + ".")
        a("")
    a("D_int = intake-only drag (TPMC C_D, body drag excluded); v_req = D_int / ṁ is the Hall-free exhaust-velocity "
      "requirement for intake-drag compensation at the delivered flow (momentum balance only, model-derived).")
    a("")
    # 5 sensitivities
    a("## 5. Dominant sensitivities")
    a("")
    a("Per closed candidate, ranked by the largest relative change of ṁ over the nine cases; the atmosphere scenario "
      "(altitude × solar) is listed as the reference spread.")
    a("")
    for sr in doc["sensitivity_ranking"]:
        a(f"**{sr['candidate']}**")
        a("")
        a("| rank | axis | variant | max Δṁ/ṁ | max Δx_O | max ΔT_feed [K] | cases losing closure |")
        a("|---|---|---|---|---|---|---|")
        for i, e in enumerate(sr["ranked"], 1):
            a(f"| {i} | {e['axis']} | `{e['id']}` | {fmt(e['max_rel_change_mdot'], 3)} | "
              f"{fmt(e['max_abs_change_x_O'], 3)} | {fmt(e['max_abs_change_T_feed_K'], 3)} | {e['cases_losing_closure']} |")
        a("")
    a("Design axes (between candidates, design case): " + "; ".join(
        f"`{e['candidate']}` ṁ {fmt(e['mdot_design_case_kgps'] * 1e6)} mg/s, x_O {fmt(e['x_O_design_case'], 3)}"
        for e in doc["design_axis_effects_at_design_case"]) + ". ṁ scales linearly with the sizing thrust level and "
      "with (1 − backflow) (FC-01).")
    a("")
    # 6 test points
    tp = doc["test_points"]
    a("## 6. PROPOSED ground test points")
    a("")
    a("All flows are anode flows; the cathode (C-1, Xe) flow is outside this chain (lane 19). P_feed is the flight "
      "valve-outlet setpoint, recorded as a covariate (lane 25); T_feed on the ground is DI-1.10. sccm at "
      f"{SCCM_T0_K} K / {SCCM_P0_PA:.0f} Pa (check each MFC's reference). Test points exist only for closed candidates.")
    a("")
    a("### Phase 1 — Hall-only sustainment knee on N₂ (HW-0)")
    a("")
    a("| id | ṁ_N2 [mg/s] | sccm N₂ | P_feed target [Pa] | trace |")
    a("|---|---|---|---|---|")
    for t in tp["phase1_knee_N2"]:
        tr = t["trace"]
        a(f"| {t['id']} | {fmt(t['mdot_N2_mgps'])} | {fmt(t['sccm_N2'])} | {fmt(t['P_feed_target_Pa'])} | "
          f"level {tr['level']}{'/' + str(tr['of']) if 'of' in tr else ''} "
          f"({', '.join(f'{kk} = {vv}' for kk, vv in tr['from'].items())}) |")
    a("")
    a("### Phase 2 — common-condition comparison (HW-0 / HW-RF / HW-ECR)")
    a("")
    a("| id | point | gas | ṁ [mg/s] | composition | status |")
    a("|---|---|---|---|---|---|")
    for t in tp["phase2_common_condition"]:
        comp = (f"w_O2 {fmt(t['w_O2'], 3)} / w_N2 {fmt(t['w_N2'], 3)}" if "w_O2" in t else "N₂")
        a(f"| {t['id']} | {t['operating_point']} | {t['gas']} | {fmt(t.get('mdot_N2_mgps'))} | {comp} | "
          f"{t.get('value_status', 'PROPOSED')} |")
    a("")
    a("### Phase 3 — absolute demonstration across the feed envelope")
    a("")
    a("| id | case | gas | ṁ_N2 [mg/s] | ṁ_O2 [mg/s] | sccm N₂ | sccm O₂ | ground/flight particle flow | flight x_O |")
    a("|---|---|---|---|---|---|---|---|---|")
    for t in tp["phase3_absolute_demonstration"]:
        a(f"| {t['id']} | {t['trace']['case']} | {t['gas']} | {fmt(t['mdot_N2_kgps'] * 1e6)} | "
          f"{fmt(t['mdot_O2_kgps'] * 1e6) if 'mdot_O2_kgps' in t else '—'} | {fmt(t['sccm_N2'])} | "
          f"{fmt(t['sccm_O2']) if 'sccm_O2' in t else '—'} | "
          f"{fmt(t['particle_flow_ratio_ground_over_flight'], 3) if 'particle_flow_ratio_ground_over_flight' in t else '—'} | "
          f"{fmt(t['flight_x_s']['O'], 3)} |")
    a("")
    m = doc["mfc_range_requirement"]
    if m.get("candidates"):
        a("### MFC range requirement (input to W4)")
        a("")
        a(f"Over closed candidates {m['candidates']}: anode ṁ {fmt(m['mdot_min_kgps'] * 1e6)}–"
          f"{fmt(m['mdot_max_kgps'] * 1e6)} mg/s ({fmt(m['sccm_N2_min'])}–{fmt(m['sccm_N2_max'])} sccm N₂), O₂ up to "
          f"{fmt(m['O2_max_kgps'] * 1e6)} mg/s ({fmt(m['sccm_O2_max'])} sccm). Accumulation headroom (FC-08, "
          f"PROPOSED): ×{fmt(m['accumulation_factor_upper'])} → {fmt(m['mdot_max_with_accumulation_kgps'] * 1e6)} mg/s.")
        a("")
    # 7 atomic O
    ao = doc["atomic_oxygen"]
    a("## 7. Can atomic O be represented on the ground?")
    a("")
    a(f"**No, not from bottles.** {ao['why']}.")
    a("")
    a("| surrogate | definition | use | limitation |")
    a("|---|---|---|---|")
    for s in ao["surrogates"]:
        a(f"| {s['id']} | {s['definition']} | {s['use']} | {s['limitation']} |")
    a("")
    a(f"**Consequence.** {ao['consequence']}.")
    a("")
    # 8 findings
    a("## 8. Findings (stated, not fixed)")
    a("")
    a("| id | where | finding | evidence class | handling |")
    a("|---|---|---|---|---|")
    for f in doc["findings"]:
        a(f"| {f['id']} | `{f['where']}` | {f['finding']} | {f['evidence_class']} | {f['handling']} |")
    a("")
    # 9 owner decisions
    a("## 9. Owner decisions needed to freeze DI-1")
    a("")
    a("| id | question | options | recommendation |")
    a("|---|---|---|---|")
    for o in doc["owner_decisions_DI1"]:
        a(f"| {o['id']} | {o['question']} | {'; '.join(o['options'])} | {o['recommendation']} |")
    a("")
    # 10 milestones
    ms = doc["milestones"]
    a("## 10. Milestones")
    a("")
    a(f"Supports **A**. {ms['A']}")
    a("")
    a("To reach **B**:")
    a("")
    for x in ms["to_reach_B"]:
        a(f"- {x}")
    a("")
    a("To reach **C**:")
    a("")
    for x in ms["to_reach_C"]:
        a(f"- {x}")
    a("")
    a("## 11. Reproduce / verify")
    a("")
    a("```")
    a(f"python {SCRIPT_REL}           # rewrite {JSON_NAME} and {MD_NAME}")
    a(f"python {SCRIPT_REL} --check   # exit 1 unless the committed files are reproduced")
    a("python -m pytest -q tests/test_feed_state_closure.py")
    a("```")
    a("")
    a("Input files are recorded with sha256 in `provenance.input_files`; a change to any of them requires regeneration.")
    a("")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------------------ main
def _same(a, b, path="$") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys differ {sorted(set(a) ^ set(b))}"]
        out = []
        for k in a:
            out += _same(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _same(x, y, f"{path}[{i}]")
        return out
    if isinstance(a, float) and isinstance(b, (int, float)) and not isinstance(b, bool):
        return [] if math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-300) else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs are reproduced")
    args = ap.parse_args(argv)
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    doc = rnd(build())
    md = render_md(doc)
    out = REPO / OUT_DIR_REL
    jp, mp = out / JSON_NAME, out / MD_NAME
    if args.check:
        problems = []
        if not jp.exists() or not mp.exists():
            print("missing committed outputs")
            return 1
        problems += _same(json.loads(jp.read_text()), doc)
        if mp.read_text() != md:
            problems.append(f"{MD_NAME} differs")
        if problems:
            print("NOT reproduced:\n  " + "\n  ".join(problems[:20]))
            return 1
        print("OK: feed-state closure reproduced")
        return 0
    jp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    mp.write_text(md)
    print(f"wrote {jp.relative_to(REPO)} and {mp.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
