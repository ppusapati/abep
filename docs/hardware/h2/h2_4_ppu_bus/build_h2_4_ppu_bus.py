#!/usr/bin/env python3
"""H2-4 PPU and bus allocation (PS-C) on bus_power_boundary_v1 -- deterministic builder.

Follow-on ``fo_h2_4_ppu_bus`` (trigger ``T_H2_4_PPU_BUS``, owner addendum A7). H2 hardware-design / preliminary-sizing
lane, NOT an architecture-selection lane (A7 h2_scope). PRELIMINARY draft for the owner.

What it does (standard library only; reads repository files; no simulation, no Julia, nothing wired into archengine):
  * verifies the sha256 of every pinned input (owner decisions A5/A6/A7, the G0 verification and the verified
    deliverables it takes numbers from) and refuses to run on a missing or changed input (no fallback);
  * builds the H2-4 design-parameter table (H24-nn), the per-component load list on bus_power_boundary_v1 (every row an
    ALLOCATION or a PARAMETER, never a Hall performance prediction), the converter-efficiency parameters (published
    analog ranges, labelled analog), the three bus profiles (STEADY / STARTUP / PEAK), the margin table (A5 allocation
    vs the 1.5 kW requirement, with the reserved pre-ionizer slot headroom as a function of the unknown discharge share),
    the PPU architecture options, the grounding scheme, the H-1 ground-supply vs flight-PPU distinction with the P_bus
    reconstruction rule, and the A7 H2 sections (interface_demands, hard_incompatibility_check,
    architecture_changing_blockers_touched, m16_rows, h3_procurement_inputs, h4_test_inputs, milestone statement);
  * writes h2_4_ppu_bus_v1.json and H2_4_PPU_BUS.md (generated from the JSON).

No Hall discharge load is predicted: the discharge power is an ALLOCATION derived from the A5 P_bus allocation minus the
auxiliary envelope (A7 blocker-2 context), never from a transport closure (credible set empty), never from
abep_sim/plasma_devices.py (superseded 0-D Hall) and never from the withdrawn v1.2-v1.6 numbers.

    python docs/hardware/h2/h2_4_ppu_bus/build_h2_4_ppu_bus.py            # (re)write the outputs
    python docs/hardware/h2/h2_4_ppu_bus/build_h2_4_ppu_bus.py --check    # byte-for-byte reproduction check (exit 1 on drift)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
OUT_JSON = os.path.join(HERE, "h2_4_ppu_bus_v1.json")
OUT_MD = os.path.join(HERE, "H2_4_PPU_BUS.md")
SCRIPT_REL = "docs/hardware/h2/h2_4_ppu_bus/build_h2_4_ppu_bus.py"
LANE_DIR = "docs/hardware/h2/h2_4_ppu_bus/"

VERSION = "h2_4_ppu_bus_v1"
BOUNDARY_VERSION = "bus_power_boundary_v1"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
DATE = "2026-09-27"
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
COMMON = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
          "thermal_control", "housekeeping")
PREION = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}
REPRESENTATIVENESS = ("FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY")
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
M16_STATES = ("READY", "RUNNING", "BLOCKED", "VERIFIED")
ROLLUPS = ("architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
           "proposal-only documentation gap")

# Parallel lanes (A6 / H2). Never read at build or test time: every dependent value is carried as PENDING <path>.
LANES = {
    "H2-1": "docs/hardware/h2/h2_1_hall_chamber_magnet/",
    "H2-2": "docs/hardware/h2/h2_2_cathode_integration/",
    "H2-3": "docs/hardware/h2/h2_3_gas_path_plenum/",
    "H2-5": "docs/hardware/h2/h2_5_thermal_network/",
    "H2-6": "docs/hardware/h2/h2_6_diagnostics_fixture/",
    "H2-7": "docs/hardware/h2/h2_7_mechanical_bom/",
    "PMI": "docs/interfaces/preionizer_module/ (+ schemas/interfaces/preionizer_module_icd_v1.json)",
    "XE": "docs/budgets/xe_ledger/",
    "P1-PREG": "docs/experiments/phase1_prereg_framework/",
    "M16": "docs/budgets/subsystem_maturity/",
}


def pend(lane: str, what: str = "") -> str:
    return f"PENDING {LANES[lane]}" + (f" ({what})" if what else "")


class H24InputError(RuntimeError):
    """A pinned input is missing, changed, or lacks an entry this build needs (no fallback)."""


# ------------------------------------------------------------------------------------------------ pinned inputs
# key -> (path, sha256 at the base commit, role). Only immutable inputs: owner decisions, the G0 verification and
# verified (merged) deliverables. Mutable governance files (lane/trigger registries, ledgers, runtime_state) are never
# pinned or read.
INPUTS = {
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
           "owner decision: proposal reference architecture, allocations, operating modes"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
           "owner decision: follow-on authorization, not_authorized list, execution-order clarification"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
           "owner decision: execution model, H2 scope, architecture-changing blockers, M16 states"),
    "G0": ("docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
           "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
           "G0 governance baseline (verdict CLEAN: A5 may be pinned)"),
    "EC": ("docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
           "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501",
           "verified deliverable (lane 20): conversion-efficiency and load evidence entries"),
    "AUX": ("docs/architecture_comparison/aux_bus/aux_bus_comparison_v1.json",
            "db4792bf65e041895e26206e122e54e944a742dc0aba467d7b0241706584bd57",
            "verified deliverable (fo_aux_bus_comparison): source-term floors and chain bus-per-watt factors"),
    "CI": ("docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
           "df020bfe3ef87b0fc6f49c56db7e38dc585c4640b5c89dd167d1f18e928dbd6f",
           "verified deliverable (lane 19): cathode heater/keeper parameters and start-up phase order"),
    "HW": ("docs/experiments/hardware/hardware_requirements_v1.json",
           "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
           "verified deliverable (fo_hardware_definition): configuration items, V_d set, I_d bound, RFP power limit"),
    "CD": ("docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json",
           "79f6b28f65243b54894dc78172b708693f96c639089f472d91d070012a0e4a52",
           "verified deliverable (compressor down-selection): PROPOSED power allocation fraction, pneumatic band"),
    "L1": ("docs/architecture_comparison/lock1/lock1_decision_brief_v1.json",
           "7ce17e1f9101d0832a164e453fd757a813f5e1e77f689cfb661bdc920f453920",
           "verified deliverable (LOCK-1 brief): lock1_inputs and decision D-11"),
    "INS": ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
            "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
            "verified deliverable (W4 instrumentation): INS-02 bus-power metering principle"),
    "PB": ("docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md",
           "2432edb7e9095fd630585768a62a811140b5230ba035afa3f0fc168636d11ca9",
           "verified deliverable (bus_power_boundary_v1 lane): Sec. 2 two-bus PPU analog (E2), Sec. 6 ppu.py finding 8"),
    "BND": ("abep_sim/arch_boundary.py",
            "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae",
            "bus_power_boundary_v1 module (read-only; component set checked textually, never imported by this builder)"),
    "PPU": ("abep_sim/ppu.py",
            "56879d06242761774830a38b421dd2b367bc8fe16c02eab88cb40e0db7d4c521",
            "legacy converter model (read-only; provenance check only: no value is taken from it)"),
}

# External sources accessed openly on DATE (no paywall, no contact). sha256 of the file actually read.
EXTERNAL = {
    "S-OSUGA05": {
        "citation": "H. Osuga et al., 'Development Status of Power Processing Unit for 200mN-class Hall Thruster', "
                    "IEPC-2005-114, 29th IEPC, Princeton University, 2005",
        "url": "https://electricrocket.org/IEPC/114.pdf",
        "sha256_accessed": "2d26151b82c67fe6b0393fc9c4bced7d6940e655a1470aa7f2ece0184b4c3cc7",
        "accessed": DATE, "access": "open"},
    "S-OSUGA09": {
        "citation": "H. Osuga et al., 'Performance of Power Processing Unit for 250mN-class Hall Thruster', "
                    "IEPC-2009-117, 31st IEPC, Ann Arbor, 2009",
        "url": "https://electricrocket.org/IEPC/IEPC-2009-117.pdf",
        "sha256_accessed": "548e8c0bfafc5f96545ac8d3547dd7e5ceba3116f5a1cd44794e49cae3974feb",
        "accessed": DATE, "access": "open"},
    "S-NIKRANT22": {
        "citation": "A. W. Nikrant et al., 'Overview and Performance Characterization of Northrop Grumman's 1 kW Hall "
                    "Thruster String', IEPC-2022-303, 37th IEPC, Boston, 2022",
        "url": "https://ntrs.nasa.gov/api/citations/20220007774/downloads/20220513%20IEPC-2022-303_FINAL.pdf",
        "sha256_accessed": "425c0d1dae3959b51aa8699d2dd89b42f19ea487658d09b3206646abbf06cf6c",
        "accessed": DATE, "access": "open",
        "note": "same file (same sha256) as S-NIKRANT22 in electrical_closure_data_v1.json; re-read on this date"},
}

# Values transcribed by hand from the external sources above (evidence carried per value; nothing here is a default).
# They are NOT repository data and cannot be recomputed from the repository: re-verification means re-reading the
# accessed file (sha256_accessed) at the locator given. Evidence-class convention used for Osuga 2005: a value from
# Table 1 'minimum efficiency' is a developer REQUIREMENT/specification -> 'assumed' (H24-06, H24-08..H24-11); the
# keeper conditioner statement of Sec. III.B ('Efficiency of keeper conditioner is more than 80%') is a reported test
# result -> 'measured' (H24-07, a lower bound only). Same document, different kinds of statement.
OSUGA05_TABLE1 = {  # IEPC-2005-114 Sec. II.B 'Requirements of the PPU', Table 1 (DM PPU output power requirements)
    "locator": "Sec. II.B, Table 1 'DM PPU output power requirements' (column 'minimum efficiency (%) at maximum "
               "power'); regulated 100 V +/- 3 V bus (requirement 1)",
    "rows": {
        "keeper":     {"V": 25.0, "I_A": [0.5, 1.0], "P_max_W": 25.0, "eta_min": 0.80, "regulation": "C.C."},
        "heater":     {"V": 40.0, "I_A": [2.0, 4.0], "P_max_W": 160.0, "eta_min": 0.85, "regulation": "C.C."},
        "inner_magnet": {"V": 10.0, "I_A": [0.2, 2.0], "P_max_W": 5.0, "eta_min": 0.60, "regulation": "C.C."},
        "outer_magnet": {"V": 12.0, "I_A": [0.2, 0.6], "P_max_W": 5.0, "eta_min": 0.60, "regulation": "C.C."},
        "mass_flow":  {"eta_min": 0.80, "regulation": "C.V.",
                       "outputs": "+/-15 V outputs; the per-output power cells are ambiguous in the extracted table "
                                  "layout and are not used"},
        "auxiliary":  {"P_max_W": 30.0, "eta_min": 0.70, "regulation": "C.V.",
                       "outputs": "-15 V 0.5 A 7.5 W; +15 V 1.5 A 22.5 W; 'supplies internal signal circuit' (Sec. IV.D)"},
        "anode":      {"V": [200.0, 300.0], "I_A": [5.0, 15.0], "P_max_W": 3000.0, "eta_min": 0.92, "regulation": "C.V."},
    },
    "keeper_measured": {"value": 0.80, "kind": "lower bound ('more than 80%')",
                        "locator": "Sec. III.B 'Keeper power conditioner' ('Efficiency of keeper conditioner is more "
                                   "than 80% at output current range from 0.9 to 1.0A at output power 25W constant')",
                        "evidence_class": "measured"},
    "floating": {"locator": "Sec. II.A item 2 ('These supplies must be floating')"},
    "magnet_topology": {"locator": "Sec. IV.C ('dynamic current controlled buck'; two-stage 'post regulator method': "
                                   "isolation converter to 15 V, then buck; maximum 2 A, 20 W)"},
    "heater_topology": {"locator": "Sec. IV.B (heater 'used before hall thruster start up'; maximum 4 A, 160 W; "
                                   "square-wave, double-forward converter at 200 kHz)"},
}
OSUGA09 = {"floating_locator": "Sec. II.B item (2) ('power conditioners supplies must be floating from the primary bus')",
           "sequencer_locator": "Sec. II.B item (4) ('The PPU automatically controls and surveys the thruster "
                                "operation of start-up, stop, failure recovery')"}
NIKRANT22 = {"locator": "Sec. II, p. 4",
             "bus_V": [24.0, 34.0], "discharge_out_W": 1000.0, "discharge_out_V": [200.0, 400.0],
             "ppu_mass_kg": 6.1,
             "supplies": "discharge supply module; heater-ignitor-keeper supply; magnet supply; PFCV supply; "
                         "microcontroller; and AUX supply",
             "discharge_topology": "zero-volt-switching full-bridge converter",
             "pfcv_control": "closed-loop control of the discharge current via the PFCV (p. 4-5)"}


KEEPER_V_HI = 35.0  # CK-PEDRINI17-HC3 locator text '14 - 35 V' (checked in build())
RHODES_SERIES = ("HD-RH24-250V-25Vin", "HD-RH24-250V-28Vin", "HD-RH24-250V-34Vin",
                 "HD-RH24-400V-25Vin", "HD-RH24-400V-28Vin", "HD-RH24-400V-34Vin")


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inputs() -> dict:
    out = {}
    for key, (rel, sha, _role) in INPUTS.items():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            raise H24InputError(f"pinned input {key} missing: {rel}")
        got = _sha(p)
        if got != sha:
            raise H24InputError(f"pinned input {key} changed: {rel} sha256 {got} != pinned {sha}")
        if rel.endswith(".json"):
            with open(p, encoding="utf-8") as f:
                out[key] = json.load(f)
        else:
            with open(p, encoding="utf-8") as f:
                out[key] = f.read()
    return out


def sig(x: float, n: int = 6) -> float:
    if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(float(x)):
        raise H24InputError(f"non-finite number {x!r}")
    return float(f"{float(x):.{n}g}") + 0.0


def need(cond: bool, msg: str) -> None:
    if not cond:
        raise H24InputError(msg)


def ec_entry(inp: dict, comp: str, eid: str) -> dict:
    for e in inp["EC"]["components"][comp]["entries"]:
        if e["id"] == eid:
            return e
    raise H24InputError(f"electrical_closure entry {comp}/{eid} missing")


def ci_param(inp: dict, key: str) -> dict:
    p = inp["CI"]["parameters"].get(key)
    need(p is not None, f"cathode_integration parameter {key} missing")
    return p


def hw_out(inp: dict, key: str) -> dict:
    d = inp["HW"]["derived_numbers"]
    v = d["outputs"].get(key) or d["inputs"].get(key)
    need(v is not None, f"hardware_requirements derived number {key} missing")
    return v


# ------------------------------------------------------------------------------------------------ extraction
def extract(inp: dict) -> dict:
    a5 = inp["A5"]
    alloc = {x["quantity"]: x for x in a5["allocations_and_requirements"]}
    need(alloc["bus-power design allocation"]["value"] == "<= 1.30-1.35 kW", "A5 bus allocation text changed")
    need(alloc["thrust operating target"]["value"] == "15-22 mN", "A5 thrust allocation text changed")
    need(alloc["absolute RFP thrust envelope"]["value"] == "12-25 mN", "A5 RFP thrust text changed")
    need(a5["operating_modes"]["nominal_mode"] == "atmospheric Hall discharge with Xe-fed cathode", "A5 nominal mode")
    need(a5["architecture"]["baseline_subsystem_count"] == 16, "A5 subsystem count")
    need(inp["G0"]["verdict"] == "CLEAN" and inp["G0"]["a5_sha256"] == INPUTS["A5"][1], "G0 verdict / A5 pin")
    need(inp["A7"]["follows_sha256"] == [INPUTS["A5"][1], INPUTS["A6"][1]], "A7 follows pins")

    # boundary component set, checked textually (the builder never imports abep_sim)
    bnd = inp["BND"]
    need('BOUNDARY_VERSION = "bus_power_boundary_v1"' in bnd, "boundary version text")
    for c in COMMON + ("rf_source", "ecr_source", "ecr_magnet"):
        need(f'"{c}"' in bnd, f"boundary component {c} missing from arch_boundary.py")

    # discharge-supply efficiency (Rhodes 2024 slide 11, all digitized input voltages 25 / 28 / 34 V, 250 / 400 V out):
    # the bus voltage is a 24-34 V PARAMETER (H24-04), so the efficiency range spans every measured input voltage
    series = {}
    for eid in RHODES_SERIES:
        e = ec_entry(inp, "hall_discharge", eid)
        need(e["evidence_class"] == "digitized", f"{eid} class")
        series[eid] = e["value"]
    pts = [p for s in series.values() for p in s]
    eta_all = [min(p["efficiency"] for p in pts), max(p["efficiency"] for p in pts)]
    # nominal 500 W step and above: the digitized 500 W points sit at 499.8-500.1 W (digitization jitter), so the
    # cut is at 499.5 W to keep the 500 W step of every input voltage (incl. 34 V / 400 V, 0.8583)
    pts500 = [p for p in pts if p["P_out_W"] >= 499.5]
    eta_500 = [min(p["efficiency"] for p in pts500), max(p["efficiency"] for p in pts500)]

    fc = ec_entry(inp, "flow_control", "FC-MOOG-I2R")
    fcs = ec_entry(inp, "flow_control", "FC-MOOG-SPEC")
    rf_nw = ec_entry(inp, "rf_source", "RF-NEWORBIT25")
    rf_vk = ec_entry(inp, "rf_source", "RF-VOLKMAR18")
    ec_tw = ec_entry(inp, "ecr_source", "EC-HAYABUSA-TWTA")
    hm_eff = ec_entry(inp, "hall_magnet", "HM-SUPPLY-EFF")
    ck_eff = ec_entry(inp, "cathode_keeper", "CK-SUPPLY-EFF")
    ch_eff = ec_entry(inp, "cathode_heater", "CH-SUPPLY-EFF")
    ch_mont = ec_entry(inp, "cathode_heater", "CH-MONTERO24")
    ck_hc3 = ec_entry(inp, "cathode_keeper", "CK-PEDRINI17-HC3")
    ck_hc1 = ec_entry(inp, "cathode_keeper", "CK-PEDRINI17-HC1")

    hc1_hp = ci_param(inp, "hc1_heater_power_W")
    hc1_ht = ci_param(inp, "hc1_heating_time_s")
    jpl_pre = ci_param(inp, "jpl_1p5cm_preheat_min")
    jpl_hmax = ci_param(inp, "jpl_1p5cm_heater_max_W")
    jpl_kV_ign = ci_param(inp, "jpl_ignition_keeper_voltage_V")
    jpl_kI = ci_param(inp, "jpl_ignition_keeper_current_A")
    jpl_kV = ci_param(inp, "jpl_keeper_voltage_after_ignition_V")
    jpl_imin = ci_param(inp, "jpl_1p5cm_min_current_without_keeper_A")
    gk_kign = ci_param(inp, "gk_keeper_ignition_voltages_V")
    hc1_kign = ci_param(inp, "hc1_ignition_keeper_voltage_V")
    need(inp["CI"]["startup_reference"]["hall_only"]["phases"][0]["name"] == "preheat", "CI start-up phase order")

    vd_set = hw_out(inp, "V_d_proposed_set_V")
    vd_relax = hw_out(inp, "V_d_relaxed_upper_V")
    p_max = hw_out(inp, "power_max_W")
    id_bound = hw_out(inp, "I_d_bound_envelope_max_A")
    need(p_max["value"] == 1500.0 or p_max["value"] == 1500, "RFP power_max_W")
    cis = {c["id"] for c in inp["HW"]["configuration_items"]}
    need({"H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR", "DIV-1"} <= cis, "HW CI ids")
    planes = {p["id"] for p in inp["HW"]["interface_planes"]}
    need({"IP-UP", "IP-DN", "HALL_INLET_Z0"} <= planes, "HW interface planes")

    comp_frac = inp["CD"]["proposed_levels"]["compressor_power_allocation_frac"]["value"]
    pneu = inp["CD"]["requirement_summary"]["P_pneumatic_eta_0p01_W"]["max"]

    aux = inp["AUX"]["components"]
    eps_n2 = aux["rf_source"]["modes"]["steady"]["load"]["lower_bound"]["floors"]["N2_feed"]["W_per_A"]
    eps_xe = aux["rf_source"]["modes"]["steady"]["load"]["lower_bound"]["floors"]["Xe_feed"]["W_per_A"]
    rf_bpw = aux["rf_source"]["modes"]["steady"]["bus_draw"]["bus_W_per_W_load"]
    ecr_bpw = aux["ecr_source"]["modes"]["steady"]["bus_draw"]["bus_W_per_W_load_reference_chain"]
    ecr_stage = aux["ecr_source"]["modes"]["steady"]["bus_draw"]["bus_W_per_W_load_at_least_for_stage_technology"]
    need(isinstance(ecr_stage, dict) and ecr_stage, "AUX ecr_source stage-technology factors missing")

    d11 = [d for d in inp["L1"]["decisions"] if isinstance(d, dict) and d.get("id") == "D-11"]
    ins02 = json.dumps(inp["INS"]).find("INS-02")
    need(ins02 >= 0, "INS-02 missing from instrumentation definition")

    pb = inp["PB"]
    need("## 6. DISCREPANCY AUDIT" in pb and "8. **Converter efficiencies are model parameters.**" in pb
         and "| E2 |" in pb and "keeper and heater from 28 V, discharge from 120 V" in pb,
         "BUS_POWER_BOUNDARY anchors (Sec. 6 finding 8, E2 two-bus PPU)")
    ppu_src = inp["PPU"]
    need("P_fixed_W: float = 3.0" in ppu_src and "controller_W: float = 8.0" in ppu_src, "ppu.py provenance anchors")

    return {
        "B_alloc_W": [1300.0, 1350.0], "R_W": float(p_max["value"]), "T_alloc_mN": [15.0, 22.0], "T_rfp_mN": [12.0, 25.0],
        "rhodes": series, "eta_d_all": eta_all, "eta_d_500": eta_500,
        "fc": fc, "fcs": fcs, "rf_nw": rf_nw, "rf_vk": rf_vk, "ec_tw": ec_tw, "hm_eff": hm_eff, "ck_eff": ck_eff,
        "ch_eff": ch_eff, "ch_mont": ch_mont, "ck_hc3": ck_hc3, "ck_hc1": ck_hc1,
        "hc1_hp": hc1_hp, "hc1_ht": hc1_ht, "jpl_pre": jpl_pre, "jpl_hmax": jpl_hmax, "jpl_kV_ign": jpl_kV_ign,
        "jpl_kI": jpl_kI, "jpl_kV": jpl_kV, "jpl_imin": jpl_imin, "gk_kign": gk_kign, "hc1_kign": hc1_kign,
        "vd_set": vd_set["value"], "vd_relax": vd_relax["value"], "id_bound": id_bound["value"],
        "comp_frac": comp_frac, "pneu_W": pneu, "eps_n2": eps_n2, "eps_xe": eps_xe, "rf_bpw": rf_bpw, "ecr_bpw": ecr_bpw,
        "ecr_stage": ecr_stage, "ecr_stage_min": min(ecr_stage.values()),
        "ecr_stage_min_id": min(ecr_stage, key=lambda k: ecr_stage[k]),
        "d11_present": bool(d11),
    }


# ------------------------------------------------------------------------------------------------ helpers
def src(key: str, locator: str) -> str:
    if key in INPUTS:
        return f"{INPUTS[key][0]} :: {locator}"
    if key in EXTERNAL:
        return f"{key} ({EXTERNAL[key]['citation']}) :: {locator}"
    if key == "THIS":
        return f"{SCRIPT_REL} :: {locator}"
    raise H24InputError(f"unknown source key {key}")


def P(pid, name, value, units, basis, source, ev, status, rep, ci, component=None, note=None):
    need(basis in BASES, f"{pid} basis {basis}")
    need(ev in EVIDENCE_CLASSES or ev.startswith("TBD"), f"{pid} evidence class {ev}")
    need(rep in REPRESENTATIVENESS, f"{pid} representativeness {rep}")
    need(status == "PRELIMINARY" or status.startswith("PENDING ") or status.startswith("TBD - requires "),
         f"{pid} status {status}")
    d = {"id": pid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": ev, "status": status, "representativeness": rep, "configuration_items": ci}
    if component:
        d["bus_component"] = component
    if note:
        d["note"] = note
    return d


# ------------------------------------------------------------------------------------------------ build
def build(inp: dict) -> dict:
    x = extract(inp)
    B = x["B_alloc_W"]
    R = x["R_W"]
    eta_d = x["eta_d_500"]
    o = OSUGA05_TABLE1["rows"]

    # ---------------------------------------------------------------- screening envelope of the common auxiliaries
    # (steady, hall_only baseline, bus side). Each term: load envelope / efficiency lower bound. Envelope values are
    # analog RATINGS or brackets used as a sizing envelope, never a Vyovrinda load.
    mag_load_hi = 60.0      # Rhodes 2024 slide 3 electromagnet-supply rating (via EC HM-SUPPLY-EFF applicability)
    need("60 W max" in x["hm_eff"]["applicability"]["notes"], "HM-SUPPLY-EFF rating text")
    eta_mag_lo = o["inner_magnet"]["eta_min"]
    keep_load_hi = max(x["ck_hc3"]["value"]["max"], x["ck_hc1"]["value"]["max"])
    need("14 - 35 V" in x["ck_hc3"]["locator"], "CK-PEDRINI17-HC3 keeper-voltage text")
    eta_keep_lo = o["keeper"]["eta_min"]
    pfcv = [x["fc"]["value"]["min"], x["fc"]["value"]["max"]]
    eta_fc_lo = o["mass_flow"]["eta_min"]
    hk_load_hi = o["auxiliary"]["P_max_W"]
    eta_hk_lo = o["auxiliary"]["eta_min"]
    comp_bus = x["comp_frac"] * R
    eta_heat_lo = o["heater"]["eta_min"]

    env = {
        "hall_magnet": {"load_W": [0.0, mag_load_hi], "eta_lower": eta_mag_lo,
                        "bus_W": [0.0, sig(mag_load_hi / eta_mag_lo)],
                        "basis": "0 W = permanent-magnet option (definition, HM-PM-OPTION); upper = analog supply "
                                 "RATING 60 W (Rhodes 2024 slide 3) at the analog minimum magnet-supply efficiency 0.60 "
                                 "(Osuga 2005 Table 1); sizing envelope only", "status": pend("H2-1", "P_mag at setpoint, hot coil")},
        "cathode_keeper": {"load_W": [0.0, keep_load_hi], "eta_lower": eta_keep_lo,
                           "bus_W": [0.0, sig(keep_load_hi / eta_keep_lo)],
                           "basis": "0 W = keeper off after ignition (Goebel & Katz p. 337, CK-G&K-OFF); upper = "
                                    "keeper-only bracket maximum (CK-PEDRINI17-HC3) at the analog keeper-supply "
                                    "efficiency lower bound 0.80 (Osuga 2005)", "status": pend("H2-2", "steady keeper policy")},
        "cathode_heater": {"load_W": [0.0, 0.0], "eta_lower": 1.0, "bus_W": [0.0, 0.0],
                           "basis": "0 W with efficiency 1 (boundary convention) CONDITIONAL on cathode self-heating at "
                                    "the steady discharge current (CH-G&K-STEADY-OFF); see HI-06",
                           "status": pend("H2-2", "self-heating current of C-1")},
        "flow_control": {"load_W": [pfcv[0], pfcv[1]], "eta_lower": eta_fc_lo,
                         "bus_W": [sig(pfcv[0]), sig(pfcv[1] / eta_fc_lo)],
                         "basis": "one energized Xe PFCV (cathode feed) in steady mode, coil I^2R 0.4191-1.46 W "
                                  "(FC-MOOG-I2R), analog valve-driver efficiency lower bound 0.80 (Osuga 2005 mass-flow "
                                  "PC); atmospheric metering valve NOT included", "status": pend("H2-3", "valve count, atmospheric metering valve power")},
        "compressor": {"load_W": None, "eta_lower": None, "bus_W": [None, sig(comp_bus)],
                       "basis": f"PROPOSED screening allocation {x['comp_frac']} x {R:g} W (compressor_downselect "
                                f"OD-C2, owner decision open) used as the bus-draw ceiling of the envelope; lower end TBD "
                                f"(pneumatic band <= {sig(x['pneu_W'])} W at 1 % efficiency excludes the fixed motor/"
                                "bearing/control loads)", "status": pend("H2-3", "compressor motor-drive input power")},
        "thermal_control": {"load_W": None, "eta_lower": None, "bus_W": [None, None],
                            "basis": "no accessed source; carried symbolically as A_th >= 0",
                            "status": pend("H2-5", "thermal_control heater duty per mode")},
        "housekeeping": {"load_W": [None, hk_load_hi], "eta_lower": eta_hk_lo, "bus_W": [None, sig(hk_load_hi / eta_hk_lo)],
                         "basis": "analog auxiliary-supply RATING 30 W output ('supplies internal signal circuit') at the "
                                  "analog minimum efficiency 0.70 (Osuga 2005 Table 1, 3 kW-class PPU); never 0 W; "
                                  "screening only", "status": pend("H2-6", "flight sensor and controller power")},
    }
    known_hi = sig(sum(env[c]["bus_W"][1] for c in ("hall_magnet", "cathode_keeper", "flow_control", "compressor",
                                                     "housekeeping")))
    known_hi_pm_off = sig(env["flow_control"]["bus_W"][1] + comp_bus + env["housekeeping"]["bus_W"][1])
    known_lo = sig(env["flow_control"]["bus_W"][0])

    # ---------------------------------------------------------------- discharge allocation (derived upper bounds)
    def d_alloc(Bw, A):
        dbus = Bw - A
        return {"B_alloc_W": Bw, "A_common_W": sig(A), "discharge_bus_W_max": sig(dbus),
                "P_d_load_W_max": [sig(dbus * eta_d[0]), sig(dbus * eta_d[1])],
                "discharge_supply_loss_W": [sig(dbus * (1 - eta_d[1])), sig(dbus * (1 - eta_d[0]))]}
    dalloc = {"envelope_high": [d_alloc(b, known_hi) for b in B],
              "permanent_magnet_keeper_off": [d_alloc(b, known_hi_pm_off) for b in B]}
    pd_hi = max(d["P_d_load_W_max"][1] for v in dalloc.values() for d in v)
    pd_lo = min(d["P_d_load_W_max"][0] for v in dalloc.values() for d in v)
    vd_all = sorted(set(x["vd_set"] + [x["vd_relax"]]))
    id_table = [{"V_d_V": v, "I_d_A_at_P_d_alloc_max": [sig(pd_lo / v), sig(pd_hi / v)]} for v in vd_all]

    # jet-power necessary bound: P_d >= T^2 / (2 mdot) at efficiency 1 -> mdot_min = T^2 / (2 P_d)
    # Cases: 'envelope' = P_d at the H24-24 allocation (CONDITIONAL on the A_common screening envelope);
    # 'known_lower_aux' = the largest discharge load compatible with the allocation when only the known lower auxiliary
    # term (one Xe PFCV coil, H24-23 known_lower_W) is booked: the weakest (unconditional within B_alloc) flow floor.
    pd_abs = sig((B[1] - known_lo) * eta_d[1])
    jet = []
    for T in sorted(set(x["T_alloc_mN"] + x["T_rfp_mN"])):
        for case, Pd in (("envelope", pd_lo), ("envelope", pd_hi), ("known_lower_aux", pd_abs)):
            m = (T * 1e-3) ** 2 / (2.0 * Pd)
            jet.append({"T_mN": T, "case": case, "P_d_alloc_W": Pd, "mdot_min_mg_s": sig(m * 1e6)})
    tp_floor = [{"T_mN": T, "B_W": b, "T_over_Pbus_min_mN_per_kW": sig(T / (b / 1000.0))}
                for T in x["T_alloc_mN"] for b in B]

    # bus input current (bus voltage is a PARAMETER: 28 V class analog set, not selected)
    vbus = NIKRANT22["bus_V"]
    ibus = [{"P_bus_W": p, "V_bus_V": v, "I_bus_A": sig(p / v)} for p in (B[0], B[1], R) for v in (vbus[0], 28.0, vbus[1])]

    # ---------------------------------------------------------------- margin table / headroom
    fgrid = [round(0.40 + 0.05 * i, 2) for i in range(12)]          # discharge bus share of B (0.40 .. 0.95)
    agrid = [0.0, 100.0, 200.0, 300.0, 400.0, known_hi, 600.0, 700.0]
    head = []
    for b in B:
        for A in agrid:
            for f in fgrid:
                ha = b * (1 - f) - A
                hb = R - f * b - A
                head.append({"B_alloc_W": b, "A_common_W": sig(A), "f_discharge_bus_share": f,
                             "discharge_bus_W": sig(f * b), "H_inside_allocation_W": sig(ha),
                             "H_inside_requirement_W": sig(hb)})
    # compact view at the screening envelope
    compact = [h for h in head if h["A_common_W"] == known_hi]
    f_zero = [{"B_alloc_W": b, "A_common_W": known_hi,
               "f_at_zero_headroom_inside_allocation": sig((b - known_hi) / b),
               "f_at_zero_headroom_inside_requirement": sig((R - known_hi) / b)} for b in B]

    # ---------------------------------------------------------------- start-up profile
    hc1_p = x["hc1_hp"]["value"]; hc1_t = x["hc1_ht"]["value"]
    hc1_pairs = [f"{p:g} W for {t:g} s" for p, t in zip(hc1_p, hc1_t)]
    jpl_t = [v * 60.0 for v in x["jpl_pre"]["value"]]
    heat_bracket = [min(hc1_p), x["ch_mont"]["value"]["max"]]
    heat_bus = [heat_bracket[0], sig(heat_bracket[1] / eta_heat_lo)]
    k_ign = [sig(x["jpl_kI"]["value"] * x["jpl_kV"]["value"][0]), sig(x["jpl_kI"]["value"] * x["jpl_kV"]["value"][1])]
    k_ign_bus = [k_ign[0], sig(k_ign[1] / eta_keep_lo)]
    pfcv_bus_hi = env["flow_control"]["bus_W"][1]
    hk_bus_hi = env["housekeeping"]["bus_W"][1]
    mag_bus_hi = env["hall_magnet"]["bus_W"][1]
    s1 = sig(heat_bus[1] + hk_bus_hi)
    s2 = sig(s1 + k_ign_bus[1] + pfcv_bus_hi)
    s3 = sig(s2 + mag_bus_hi)
    s4 = sig(s3 + pfcv_bus_hi)
    # transition keeper term: the keeper is still on (A5 transition; C-1 policy PENDING H2-2). It is booked at the
    # larger of the ignition bracket and the steady keeper envelope, i.e. the same term PK-2 uses (consistency).
    keep_trans_bus = max(k_ign_bus[1], env["cathode_keeper"]["bus_W"][1])
    s5_aux = sig(keep_trans_bus + mag_bus_hi + 2 * pfcv_bus_hi + comp_bus + hk_bus_hi)
    need(abs(s5_aux - sig(known_hi + pfcv_bus_hi)) < 1e-3, "SU-5 and PK-2 must book the same transition state")
    phases = [
        {"id": "SU-0", "a5_mode": "OFF", "name": "off / standby", "on": ["housekeeping"],
         "duration": "unbounded (standby)", "known_bus_W_upper": sig(hk_bus_hi),
         "open_terms": ["housekeeping standby (v1: booked under housekeeping)", "thermal_control survival heaters (H2-5)"]},
        {"id": "SU-1", "a5_mode": "Xe ignition/startup", "name": "cathode heater preheat",
         "on": ["cathode_heater", "housekeeping"],
         "duration": {"analog_s": {"SITAEL_HC1_pairs": hc1_pairs, "JPL_1p5cm": jpl_t},
                      "status": pend("H2-2", "C-1 preheat time")},
         "loads": {"cathode_heater_W": heat_bracket}, "known_bus_W_upper": s1,
         "open_terms": ["thermal_control (H2-5)"],
         "energy_per_start_Wh_HC1_pairs": [sig(p * t / 3600.0) for p, t in zip(hc1_p, hc1_t)]},
        {"id": "SU-2", "a5_mode": "Xe ignition/startup", "name": "keeper ignition (cathode Xe flow on)",
         "on": ["cathode_heater", "cathode_keeper", "flow_control", "housekeeping"],
         "duration": "TBD - requires C-1 ignition test (S1a/S1)",
         "loads": {"cathode_keeper_W": k_ign, "keeper_open_circuit_V": "150 V DC (JPL) / 50-150 V DC + 300-600 V pulse "
                   "(Goebel & Katz) / 45-50 V with heater, up to 800 V heaterless (SITAEL HC1)",
                   "flow_control": "cathode Xe PFCV energized"},
         "known_bus_W_upper": s2, "open_terms": ["thermal_control (H2-5)"]},
        {"id": "SU-3", "a5_mode": "Xe ignition/startup", "name": "magnet ramp to setpoint (current control)",
         "on": ["cathode_heater", "cathode_keeper", "hall_magnet", "flow_control", "housekeeping"],
         "duration": pend("H2-1", "coil L/R and ramp rate"), "known_bus_W_upper": s3,
         "open_terms": ["thermal_control (H2-5)"],
         "order_note": "the magnet-vs-discharge order is not fixed by the accessed sources (cathode_integration "
                       "startup_reference.hall_only.open); the order heater -> keeper -> magnet -> Xe ignition is the "
                       "lane's PROPOSED sequence"},
        {"id": "SU-4", "a5_mode": "Xe ignition/startup", "name": "Xe discharge ignition (anode Xe via ignition PFCV)",
         "on": ["hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater (until discharge start)",
                "flow_control", "housekeeping"],
         "duration": "TBD - requires S1 ignition transients (HW-ENV-02 transient margin)",
         "known_bus_W_upper": s4,
         "open_terms": ["D_ign: discharge ignition transient bus draw (TBD, S1; bounded by the discharge-supply current "
                        "limit x V_d / eta_d)", "thermal_control (H2-5)"],
         "note": "Goebel & Katz sequence: heater off once the discharge starts; the heater term is present only up to "
                 "the ignition instant"},
        {"id": "SU-5", "a5_mode": "brief transition support", "name": "Xe -> atmospheric transition",
         "on": ["hall_discharge", "hall_magnet", "cathode_keeper", "flow_control", "compressor", "housekeeping",
                "thermal_control"],
         "duration": pend("XE", "t_transition, symbolic until H-1/C-1 measure it (A6 fo_xe_system_ledger)"),
         "known_aux_bus_W_upper": s5_aux,
         "keeper_term_note": f"keeper booked at max(ignition bracket {k_ign_bus[1]} W bus, steady keeper envelope "
                             f"{env['cathode_keeper']['bus_W'][1]} W bus) = {sig(keep_trans_bus)} W bus; equals PK-2 "
                             "(A_common envelope incl. keeper on + one extra PFCV)",
         "open_terms": ["P_d/eta_d at the transition point (allocation, not a prediction)",
                        "atmospheric metering valve (H2-3)", "thermal_control (H2-5)"],
         "rule": "A5: mixed/transition operation never silently becomes a long-duration mode; its maximum duration "
                 "draws on the fixed Xe allocation"},
        {"id": "SU-6", "a5_mode": "atmospheric Hall + Xe cathode (nominal)", "name": "keeper off / nominal steady",
         "on": ["hall_discharge", "hall_magnet", "flow_control", "compressor", "thermal_control", "housekeeping"],
         "duration": "continuous", "profile": "STEADY"},
    ]
    other_modes = [
        {"a5_mode": "degraded", "profile": "STEADY component set at reduced allocation; no additional component",
         "status": "TBD - requires the FDIR mode definition (control/FDIR row)"},
        {"a5_mode": "time-limited Xe contingency/fallback",
         "profile": "STEADY component set with the Xe anode PFCV energized; compressor may be off; bounded by "
                    "t_fallback_max (A6 fo_xe_system_ledger)", "status": pend("XE", "t_fallback_max")},
        {"a5_mode": "shutdown", "profile": "discharge off -> magnet ramp-down -> valves closed -> housekeeping",
         "status": "PRELIMINARY"},
    ]

    peak = [
        {"id": "PK-1", "name": "ignition overlap (heater still on at the discharge ignition instant)",
         "components": ["cathode_heater", "cathode_keeper", "hall_magnet", "flow_control (2 PFCV)", "housekeeping",
                        "hall_discharge (ignition transient D_ign)"],
         "known_bus_W_upper": s4, "expression": f"P_peak,1 = {s4} W + D_ign + A_th",
         "headroom_to_1500_W_for_D_ign": sig(R - s4)},
        {"id": "PK-2", "name": "transition (discharge at its allocation + keeper + both Xe PFCVs + compressor)",
         "components": ["hall_discharge", "hall_magnet", "cathode_keeper", "flow_control (2 PFCV)", "compressor",
                        "housekeeping", "thermal_control"],
         "expression": "P_peak,2 = P_d/eta_d + A_common(envelope incl. keeper on) + 1 extra PFCV",
         "extra_over_steady_envelope_W": sig(pfcv_bus_hi),
         "known_aux_bus_W_upper": s5_aux,
         "note": "at the envelope the transition peak exceeds the steady allocation only by the second Xe PFCV; the "
                 "known auxiliary term equals STARTUP SU-5 (same keeper term)"},
        {"id": "PK-3", "name": "reserved-slot seed variant V2 (pre-ionizer on before discharge ignition; NOT baseline)",
         "components": ["PK-1 components", "rf_source or ecr_source + ecr_magnet"],
         "expression": f"P_peak,3 = {s4} W + D_ign + P_bus[source] (+ P_bus[ecr_magnet]) + A_th",
         "headroom_to_1500_W_for_D_ign_plus_source": sig(R - s4),
         "note": "cathode_integration startup_reference rf_hall/ecr_hall V2; PROPOSED sequencing constraint SEQ-1 "
                 "removes the heater term from this overlap"},
        {"id": "PK-4", "name": "compressor spin-up overlapping preheat (if scheduled concurrently)",
         "expression": f"P_peak,4 = {s1} W + P_comp,spin-up (TBD, H2-3) + A_th",
         "status": pend("H2-3", "compressor start-up input power profile")},
    ]
    inrush = [
        {"id": "IR-1", "item": "PPU input-filter charging at bus connection", "value": "TBD - requires the PPU input "
         "filter design and the spacecraft EPS inrush requirement", "representativeness": "FLIGHT-REPRESENTATIVE"},
        {"id": "IR-2", "item": "discharge ignition current transient", "value": "TBD - requires S1 ignition/extinction "
         "transients (HW-ENV-02 transient margin)", "representativeness": "FLIGHT-REPRESENTATIVE"},
        {"id": "IR-3", "item": "magnet coil energization", "value": "limited by the current-controlled supply ramp "
         "(Osuga 2005 Sec. IV.C current-controlled buck); ramp rate " + pend("H2-1"),
         "representativeness": "FLIGHT-REPRESENTATIVE"},
        {"id": "IR-4", "item": "compressor motor start", "value": pend("H2-3", "motor start current"),
         "representativeness": "FLIGHT-REPRESENTATIVE"},
        {"id": "IR-5", "item": "heater cold-resistance inrush (refractory heater resistance rises with temperature)",
         "value": "TBD - requires the C-1 heater R(T); a current-regulated heater supply (Osuga 2005 C.C.) bounds it",
         "representativeness": "FLIGHT-REPRESENTATIVE"},
    ]

    # ---------------------------------------------------------------- design-parameter table (H24-nn)
    rh = "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json"
    params = [
        P("H24-01", "RFP bus-power requirement (strict upper limit)", R, "W", "requirement",
          src("HW", "derived_numbers.inputs.power_max_W (RFPConstraints.power_max_W; RFP '< 1.5 kW', verify against RFP "
                    "document)"), "assumed", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C"], "bus_power_boundary_v1 total",
          "Which boundary the RFP '< 1.5 kW' applies to is owner question BPB-OQ-1; this lane reads it at "
          "bus_power_boundary_v1 as A5 states for the allocation"),
        P("H24-02", "A5 bus-power design allocation", B, "W", "allocation",
          src("A5", "allocations_and_requirements['bus-power design allocation'] '<= 1.30-1.35 kW'"), "assumed",
          "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C"], None, "an ALLOCATION, never a prediction"),
        P("H24-03", "allocation-to-requirement margin", [sig(R - B[1]), sig(R - B[0])], "W", "derived",
          src("THIS", "R - B_alloc"), "model-derived", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C"]),
        P("H24-04", "spacecraft DC bus voltage at the propulsion input", "28 V-class unregulated (24-34 V) analog set; "
          "not selected", "V", "analog",
          src("S-NIKRANT22", "Sec. II p. 4 '24-34 V unregulated bus'") + "; " + src("EC", "HD-RH24-* applicability.bus_V "
          "[24, 34]") + "; alternative regulated 100 V (" + src("S-OSUGA05", "Sec. II.B requirement 1") + ")",
          "measured", "TBD - requires the spacecraft EPS definition (owner)", "FLIGHT-REPRESENTATIVE", ["PS-C"], None,
          "the only sub-kW discharge-supply efficiency data accessed are at 24-34 V (EC HD-RH24-*)"),
        P("H24-05", "discharge-supply efficiency eta_d (bus -> supply output), nominal P_out >= 500 W, 25-34 V in", eta_d, "-",
          "analog", src("EC", ", ".join(RHODES_SERIES) + " (Rhodes 2024 slide 11, points at the nominal 500 W step and above, all "
                        "digitized input voltages 25 / 28 / 34 V, outputs 250 / 400 V)"),
          "digitized", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C"], "hall_discharge",
          "breadboard LCC supply; harness/filters to the thruster excluded; above 1 kW output not measured; 24 V input "
          "not digitized (lowest measured input 25 V; H24-04 lists 24-34 V); the range spans the input-voltage "
          "parameter, so it propagates to every allocation derived from it (H24-24/26, MG-5..7); full "
          f"measured span 200-1000 W is {x['eta_d_all'][0]}-{x['eta_d_all'][1]}"),
        P("H24-06", "discharge-supply efficiency, 3 kW class, 100 V bus (analog, not transferable)", o["anode"]["eta_min"],
          "-", "analog", src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC1 anode"), "assumed", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C"], "hall_discharge",
          "developer-reported minimum-efficiency REQUIREMENT of a 3 kW PPU (a specification, not a measurement); context only"),
        P("H24-07", "keeper-supply efficiency lower bound (analog)", eta_keep_lo, "-", "analog",
          src("S-OSUGA05", OSUGA05_TABLE1["keeper_measured"]["locator"]) + "; spec " +
          src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC2 keeper 80 %"),
          "measured", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C", "C-1"], "cathode_keeper",
          "100 V-bus 25 W keeper conditioner; lower bound only ('more than 80%'); class 'measured' because Sec. III.B "
          "reports a test result, whereas H24-06/08-11 are Table 1 minimum-efficiency SPECIFICATIONS (class 'assumed'); "
          "transcribed external constant, not repository data; EC CK-SUPPLY-EFF stays TBD for a 28 V-class keeper supply"),
        P("H24-08", "heater-supply efficiency (analog minimum-efficiency specification)", eta_heat_lo, "-", "analog",
          src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC3 heater 85 % at 160 W"), "assumed", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C", "C-1"], "cathode_heater", "specification, not a measurement"),
        P("H24-09", "magnet-supply efficiency (analog minimum-efficiency specification)", eta_mag_lo, "-", "analog",
          src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC4/PC5 magnet 60 % at 5 W"), "assumed", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C", "MC-1"], "hall_magnet",
          "a 5 W-class output: efficiency at the Vyovrinda coil power is TBD (EC HM-SUPPLY-EFF)"),
        P("H24-10", "valve-driver (mass-flow PC) efficiency (analog minimum-efficiency specification)", eta_fc_lo, "-",
          "analog", src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC6 mass flow 80 %"), "assumed", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C", "FS-C"], "flow_control"),
        P("H24-11", "auxiliary / housekeeping supply efficiency (analog minimum-efficiency specification)", eta_hk_lo,
          "-", "analog", src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC7 auxiliary 70 %"), "assumed", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C"], "housekeeping"),
        P("H24-12", "compressor motor-drive efficiency", None, "-", "pending", pend("H2-3"),
          "TBD - requires converter data at the motor-drive input power", pend("H2-3", "motor drive selection"),
          "FLIGHT-REPRESENTATIVE", ["FS-C"], "compressor", "EC CP-CONV-EFF TBD"),
        P("H24-13", "thermal_control switch efficiency", None, "-", "pending", pend("H2-5"),
          "TBD - requires heater-switch topology data", pend("H2-5", "heater list"), "FLIGHT-REPRESENTATIVE", ["PS-C"],
          "thermal_control", "EC TC-EFF TBD"),
        P("H24-14", "rf_source chain efficiency (reserved slot; not baseline flight hardware)",
          [x["rf_vk"]["value"]["min"], x["rf_nw"]["value"]], "-", "analog",
          src("EC", "RF-VOLKMAR18 (inferred, 0.60-0.70), RF-NEWORBIT25 (measured nominal 0.92)"), "inferred",
          "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PIM-RF"], "rf_source",
          "bus per W delivered 1.08696-1.66667: ANALOG RANGE from these efficiencies, not a bound "
          "(AUX components.rf_source.bus_draw)"),
        P("H24-15", "ecr_source chain efficiency (alternate slot; not baseline flight hardware)", x["ec_tw"]["value"], "-",
          "analog", src("EC", "EC-HAYABUSA-TWTA (only system-level chain value; 4.2 GHz TWT)"), "inferred", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PIM-ECR"], "ecr_source",
          f"bus per W delivered {x['ecr_bpw']} for this REFERENCE chain only (Hayabusa TWTA; the ABEP chain may be "
          f"higher or lower, AUX ecr_source.bus_draw); necessary stage-only lower bound >= {x['ecr_stage_min']} "
          f"({x['ecr_stage_min_id']}), {sig(min(x['ecr_stage'].values()))}-{sig(max(x['ecr_stage'].values()))} by "
          "stage technology"),
        P("H24-16", "hall_magnet load envelope (steady)", env["hall_magnet"]["load_W"], "W", "analog",
          env["hall_magnet"]["basis"] + "; " + rh + " :: HM-SUPPLY-EFF applicability.notes",
          "assumed", env["hall_magnet"]["status"], "FLIGHT-REPRESENTATIVE", ["MC-1", "PS-C"], "hall_magnet",
          "PARAMETER envelope from a supply rating, not a coil load"),
        P("H24-17", "cathode_keeper load envelope (steady)", env["cathode_keeper"]["load_W"], "W", "analog",
          env["cathode_keeper"]["basis"] + "; " + rh + " :: CK-PEDRINI17-HC3", "measured", env["cathode_keeper"]["status"],
          "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"], "cathode_keeper"),
        P("H24-18", "cathode_heater load bracket (start-up)", heat_bracket, "W", "analog",
          src("CI", "parameters.hc1_heater_power_W (45 W)") + "; " + rh + " :: CH-MONTERO24 (max 305 W)", "measured",
          pend("H2-2", "C-1 heater selection"), "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"], "cathode_heater",
          "bracket across three LaB6 designs, not a C-1 value"),
        P("H24-19", "cathode_keeper ignition load bracket (start-up)", k_ign, "W", "derived",
          src("CI", "parameters.jpl_ignition_keeper_current_A (2 A) x jpl_keeper_voltage_after_ignition_V (5-15 V)"),
          "inferred", pend("H2-2", "C-1 keeper ignition current"), "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"],
          "cathode_keeper", "same product as aux_bus startup keeper bracket; JPL 1.5-cm cathode, different class"),
        P("H24-20", "flow_control per energized Xe PFCV (coil I^2R)", pfcv, "W", "analog",
          rh + " :: FC-MOOG-I2R (74.5 ohm, 75-140 mA at 21 C)", "inferred", pend("H2-3", "valve count and types"),
          "FLIGHT-REPRESENTATIVE", ["FS-C", "PS-C"], "flow_control", "valve driver loss excluded"),
        P("H24-21", "compressor bus-draw screening ceiling", sig(comp_bus), "W", "allocation",
          src("CD", "proposed_levels.compressor_power_allocation_frac (PROPOSED 0.2; OD-C2 open)"), "assumed",
          pend("H2-3", "compressor input power; owner OD-C2"), "FLIGHT-REPRESENTATIVE", ["FS-C"], "compressor",
          "PROPOSED screening allocation, not an owner allocation"),
        P("H24-22", "housekeeping bus-draw screening envelope", sig(hk_load_hi / eta_hk_lo), "W", "analog",
          env["housekeeping"]["basis"], "assumed", pend("H2-6", "sensor + controller power"), "FLIGHT-REPRESENTATIVE",
          ["PS-C"], "housekeeping"),
        P("H24-23", "screening envelope of the common auxiliaries A_common (steady, excl. thermal_control and the "
          "atmospheric metering valve)", {"envelope_high_W": known_hi, "permanent_magnet_keeper_off_W": known_hi_pm_off,
                                          "known_lower_W": known_lo}, "W", "derived",
          src("THIS", "build(): sum of H24-16/17/20/21/22 bus terms"), "model-derived", "PRELIMINARY",
          "FLIGHT-REPRESENTATIVE", ["PS-C"], None, "an envelope for allocation, not a predicted load"),
        P("H24-24", "hall_discharge ALLOCATION (load side), hall_only baseline, reserved slot empty",
          [pd_lo, pd_hi], "W", "allocation",
          src("THIS", "P_d,alloc <= eta_d x (B_alloc - A_common); eta_d H24-05; A_common H24-23"), "model-derived",
          "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["H-1", "PS-C"], "hall_discharge",
          "an upper-bound ALLOCATION derived from the A5 P_bus allocation; thermal_control and the atmospheric valve "
          "reduce it further; never a Hall performance prediction"),
        P("H24-25", "flight discharge-supply output voltage range", [min(vd_all), max(vd_all)], "V", "requirement",
          src("HW", "derived_numbers.inputs.V_d_proposed_set_V + V_d_relaxed_upper_V (PROPOSED set, HWQ-03)"),
          "assumed", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C", "H-1"], "hall_discharge"),
        P("H24-26", "flight discharge-supply output current at the allocation", [id_table[-1]["I_d_A_at_P_d_alloc_max"][0],
          id_table[0]["I_d_A_at_P_d_alloc_max"][1]], "A", "derived", src("THIS", "P_d,alloc / V_d over H24-25"),
          "model-derived", "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C"], "hall_discharge",
          "transient margin TBD (S1); allocation-derived, not a predicted discharge current"),
        P("H24-27", "H-1 laboratory discharge supply current rating (bus-compliance bound)", x["id_bound"], "A",
          "requirement", src("HW", "derived_numbers.outputs.I_d_bound_envelope_max_A (P_max / min V_d); HW-ENV-02"),
          "model-derived", "PRELIMINARY", "GROUND/FACILITY-ONLY", ["PS-C"], "hall_discharge",
          "plus a transient margin TBD - requires S1 ignition/extinction transients"),
        P("H24-28", "keeper supply ignition capability", "DC open circuit >= 150 V (JPL procedure) up to 300 V (Rhodes "
          "keeper supply DC ramp); pulse igniter 300-600 V option (Goebel & Katz); up to 800 V heaterless (SITAEL HC1)",
          "V", "analog", src("CI", "parameters.jpl_ignition_keeper_voltage_V, gk_keeper_ignition_voltages_V, "
          "hc1_ignition_keeper_voltage_V") + "; " + rh + " :: CK-SUPPLY-EFF applicability.notes (300 V open circuit)",
          "measured", pend("H2-2", "C-1 ignition voltage"), "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"], "cathode_keeper"),
        P("H24-29", "keeper supply current regulation range", [o["keeper"]["I_A"][0], x["jpl_kI"]["value"]], "A", "analog",
          src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC2 0.5-1 A") + "; " + src("CI", "parameters."
          "jpl_ignition_keeper_current_A (2 A)"), "measured", pend("H2-2", "C-1 keeper current"),
          "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"], "cathode_keeper"),
        P("H24-30", "heater supply rating envelope", {"P_W": [heat_bracket[0], x["jpl_hmax"]["value"],
          heat_bracket[1]], "I_A_analogs": {"Rhodes_rating": "1-8 A", "Osuga_PC3": "2-4 A", "JPL_1p5cm": "13 A"}},
          "W / A", "analog", rh + " :: CH-SUPPLY-EFF applicability.notes; " + src("CI", "parameters.jpl_1p5cm_heater_max_W") +
          "; " + src("S-OSUGA05", OSUGA05_TABLE1["locator"] + " PC3") + "; JPL 13 A: " +
          src("CI", "parameters.jpl_1p5cm_preheat_min locator ('typically 13 A for 18 to 20 minutes')"), "measured",
          pend("H2-2", "C-1 heater V/I/P"), "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"], "cathode_heater"),
        P("H24-31", "preheat duration (analog)", {"SITAEL_HC1_pairs": hc1_pairs, "JPL_1p5cm_s": jpl_t}, "s", "analog",
          src("CI", "parameters.hc1_heating_time_s, jpl_1p5cm_preheat_min"), "measured", pend("H2-2", "C-1 preheat"),
          "FLIGHT-REPRESENTATIVE", ["C-1"], "cathode_heater"),
        P("H24-32", "magnet supply: current control, per coil, 4-wire V sense", "current-controlled; analog ratings "
          "1-12 V / 1-5 A / 60 W (Rhodes) and 0.2-2 A / 10-12 V (Osuga PC4/PC5)", "-", "analog",
          rh + " :: HM-SUPPLY-EFF applicability.notes; " + src("S-OSUGA05", OSUGA05_TABLE1["magnet_topology"]["locator"]) +
          "; " + src("HW", "requirements HW-MC-02, HW-MC-14"), "measured", pend("H2-1", "NI, coil R(T), coil count"),
          "FLIGHT-REPRESENTATIVE", ["MC-1", "PS-C"], "hall_magnet"),
        P("H24-33", "bus input current at P_bus (harness / protection sizing)", [min(i["I_bus_A"] for i in ibus),
          max(i["I_bus_A"] for i in ibus)], "A", "derived", src("THIS", "P_bus / V_bus over {1300, 1350, 1500} W x "
          "{24, 28, 34} V"), "model-derived", "TBD - requires the spacecraft EPS definition (bus voltage)",
          "FLIGHT-REPRESENTATIVE", ["PS-C", "SVC-1"]),
        P("H24-34", "PPU architecture analog mass (1 kW, 24-34 V, EM1)", NIKRANT22["ppu_mass_kg"], "kg", "analog",
          src("S-NIKRANT22", NIKRANT22["locator"] + " 'The EM1 PPU has a mass of 6.1 kg'"), "measured",
          pend("H2-7", "PPU mass allocation"), "FLIGHT-REPRESENTATIVE", ["PS-C"], None,
          "analog only (different thruster, Xe, 1 kW class); handed to H2-7, never a Vyovrinda mass"),
        P("H24-35", "no single-point failure in electronics", "RFP_AS_RECORDED (verify against RFP document)", "-",
          "requirement", "docs/architecture_comparison/hard_gates/HARD_GATES.md 'RFP sources' (recorded, not a gate, "
                         "OD12); abep_sim/ppu.py docstring (unsourced)", "assumed",
          "TBD - requires the RFP text and an owner redundancy policy (cold/hot redundancy per supply)",
          "FLIGHT-REPRESENTATIVE", ["PS-C"], None, "redundancy changes PPU mass, not the steady P_bus"),
        P("H24-36", "PROPOSED start-up sequencing constraint SEQ-1 (heater off before compressor spin-up and before any "
          "reserved-slot seed)", "PROPOSED", "-", "assumed", src("THIS", "bus_profiles.peak PK-3/PK-4"), "assumed",
          "PRELIMINARY", "FLIGHT-REPRESENTATIVE", ["PS-C", "C-1"], None, "owner decision; removes the largest start-up "
          "term from the peak overlaps"),
        P("H24-37", "PROPOSED start-up peak rule", "P_bus,peak < 1500 W including transients (averaging window TBD)",
          "W", "assumed", src("CI", "proposed_thresholds.startup_peak_limit (PROPOSED)"), "assumed",
          "TBD - requires an owner decision (does the RFP '< 1.5 kW' bound start-up transients?)",
          "FLIGHT-REPRESENTATIVE", ["PS-C"]),
        P("H24-38", "H-1 P_bus metering channels (INS-02)", "one DC channel per bus_power_boundary_v1 component present "
          "in the lab (4-wire V + calibrated shunt / zero-flux CT, simultaneous sampling)", "-", "requirement",
          src("INS", "INS-02 principle"), "assumed", "PRELIMINARY", "H-1 TEST-ARTICLE-ONLY", ["PS-C", "SVC-1"]),
        P("H24-39", "H-1 laboratory supplies (discharge, magnet, keeper, heater)", "laboratory supplies with load-plane "
          "metering; their own conversion losses never enter P_bus", "-", "requirement",
          src("HW", "configuration_items[PS-C]; requirements HW-ENV-05"), "assumed", "PRELIMINARY",
          "GROUND/FACILITY-ONLY", ["PS-C"]),
        P("H24-41", "keeper supply steady output capability (sized to the H24-17 envelope)",
          {"P_out_W_min": keep_load_hi, "V_compliance_V_min": KEEPER_V_HI, "I_A_max": x["jpl_kI"]["value"],
           "capability_at_V_and_I_max_W": sig(KEEPER_V_HI * x["jpl_kI"]["value"])}, "W / V / A", "derived",
          rh + " :: CK-PEDRINI17-HC3 locator ('discharge power ranges from about 25 to 60 W ... discharge voltage "
          "settling in the range 14 - 35 V'); " + src("CI", "parameters.jpl_ignition_keeper_current_A (2 A)"),
          "inferred", pend("H2-2", "C-1 steady keeper policy and keeper V-I"), "FLIGHT-REPRESENTATIVE", ["C-1", "PS-C"],
          "cathode_keeper", "PROPOSED supply rating so that the keeper supply can deliver the steady keeper envelope it "
          "is budgeted for (60 W needs >= 30 V at 2 A); 5-15 V x 2 A (JPL) alone gives only 30 W; if H2-2 fixes a "
          "smaller steady keeper envelope the rating (and H24-17) shrink together"),
        P("H24-40", "discharge / keeper / heater / magnet outputs floating from the primary bus", "isolated outputs",
          "-", "analog", src("S-OSUGA05", OSUGA05_TABLE1["floating"]["locator"]) + "; " +
          src("S-OSUGA09", OSUGA09["floating_locator"]), "assumed", pend("H2-2", "cathode-common return path"),
          "FLIGHT-REPRESENTATIVE", ["PS-C", "C-1", "H-1"]),
    ]
    ids = [p["id"] for p in params]
    need(len(ids) == len(set(ids)), "duplicate parameter ids")

    # ---------------------------------------------------------------- load list (per component)
    load_list = [
        {"component": "hall_discharge", "kind": "ALLOCATION", "modes": ["steady", "startup (SU-4..SU-6)"],
         "load_W": [pd_lo, pd_hi], "V_range_V": [min(vd_all), max(vd_all)],
         "I_range_A": [id_table[-1]["I_d_A_at_P_d_alloc_max"][0], id_table[0]["I_d_A_at_P_d_alloc_max"][1]],
         "efficiency_parameter": "H24-05", "params": ["H24-24", "H24-25", "H24-26"], "status": "PRELIMINARY",
         "note": "allocation derived from the A5 P_bus allocation minus the auxiliary envelope; H-1 Phase 1 measures V_d x I_d"},
        {"component": "hall_magnet", "kind": "PARAMETER", "modes": ["steady", "startup (SU-3..)"],
         "load_W": env["hall_magnet"]["load_W"], "V_range_V": "analog 1-12 V", "I_range_A": "analog 0.2-5 A",
         "efficiency_parameter": "H24-09", "params": ["H24-16", "H24-32"], "status": env["hall_magnet"]["status"]},
        {"component": "cathode_keeper", "kind": "PARAMETER", "modes": ["startup (SU-2..SU-5)", "steady (policy)"],
         "load_W": {"steady": env["cathode_keeper"]["load_W"], "startup": k_ign},
         "V_range_V": "ignition >= 150 V open circuit (analog); 5-15 V after ignition (JPL 1.5-cm); 14-35 V keeper-only "
                      "discharge (CK-PEDRINI17-HC3, the source of the 60 W steady envelope); supply compliance >= 35 V "
                      "(H24-41)",
         "I_range_A": [o["keeper"]["I_A"][0], x["jpl_kI"]["value"]], "efficiency_parameter": "H24-07",
         "params": ["H24-17", "H24-19", "H24-28", "H24-29", "H24-41"], "status": env["cathode_keeper"]["status"]},
        {"component": "cathode_heater", "kind": "PARAMETER", "modes": ["startup (SU-1..SU-4)", "steady 0 W (conditional)"],
         "load_W": {"startup": heat_bracket, "steady": [0.0, 0.0]}, "V_range_V": "analog 1-40 V",
         "I_range_A": "analog 1-13 A", "efficiency_parameter": "H24-08", "params": ["H24-18", "H24-30", "H24-31"],
         "status": pend("H2-2", "C-1 heater")},
        {"component": "flow_control", "kind": "PARAMETER", "modes": ["all"],
         "load_W": {"per_Xe_PFCV": pfcv, "atmospheric_metering_valve": pend("H2-3")},
         "V_range_V": [sig(x["fcs"]["value"]["I_min_opening_mA"] * 1e-3 * x["fcs"]["value"]["R_coil_ohm"]),
                       sig(x["fcs"]["value"]["I_max_sustained_mA"] * 1e-3 * x["fcs"]["value"]["R_coil_ohm"])],
         "I_range_A": [x["fcs"]["value"]["I_min_opening_mA"] * 1e-3, x["fcs"]["value"]["I_max_sustained_mA"] * 1e-3],
         "efficiency_parameter": "H24-10", "params": ["H24-20"], "status": pend("H2-3", "valve count")},
        {"component": "compressor", "kind": "ALLOCATION", "modes": ["steady", "transition", "spin-up"],
         "load_W": {"bus_ceiling_W": sig(comp_bus), "pneumatic_band_eta_1pct_W": sig(x["pneu_W"])},
         "V_range_V": pend("H2-3", "motor-drive bus"), "I_range_A": pend("H2-3"),
         "efficiency_parameter": "H24-12", "params": ["H24-21"], "status": pend("H2-3", "compressor input power")},
        {"component": "thermal_control", "kind": "PARAMETER", "modes": ["all"], "load_W": pend("H2-5"),
         "V_range_V": "bus-switched (TBD)", "I_range_A": pend("H2-5"), "efficiency_parameter": "H24-13",
         "params": [], "status": pend("H2-5", "heater duty per mode")},
        {"component": "housekeeping", "kind": "PARAMETER", "modes": ["all incl. OFF/standby"],
         "load_W": {"screening_envelope_output_W": hk_load_hi}, "V_range_V": "analog +/-15 V (Osuga 2005 PC7)",
         "I_range_A": "TBD", "efficiency_parameter": "H24-11", "params": ["H24-22"],
         "status": pend("H2-6", "sensor + controller power")},
        {"component": "rf_source", "kind": "PARAMETER", "modes": ["reserved slot only (rf_hall)"],
         "load_W": "headroom function H(f) (margin_table); P_hi per LOCK-1 lock1_inputs[2]", "V_range_V": pend("PMI"),
         "I_range_A": pend("PMI"), "efficiency_parameter": "H24-14", "params": ["H24-14"],
         "status": pend("PMI", "electrical power boundary PMI-xx"), "baseline_flight_hardware": False},
        {"component": "ecr_source", "kind": "PARAMETER", "modes": ["alternate slot only (ecr_hall)"],
         "load_W": "headroom function H(f)", "V_range_V": pend("PMI"), "I_range_A": pend("PMI"),
         "efficiency_parameter": "H24-15", "params": ["H24-15"], "status": pend("PMI"), "baseline_flight_hardware": False},
        {"component": "ecr_magnet", "kind": "PARAMETER", "modes": ["alternate slot only (ecr_hall)"],
         "load_W": "0 W with efficiency 1 if permanent magnet (HWQ-05); electromagnet TBD", "V_range_V": pend("PMI"),
         "I_range_A": pend("PMI"), "efficiency_parameter": None, "params": [], "status": pend("PMI"),
         "baseline_flight_hardware": False},
    ]
    need([r["component"] for r in load_list] == list(COMMON) + ["rf_source", "ecr_source", "ecr_magnet"],
         "load list must cover exactly the bus_power_boundary_v1 components")

    steady_rows = []
    for c in COMMON:
        e = env.get(c)
        if c == "hall_discharge":
            steady_rows.append({"component": c, "kind": "ALLOCATION", "bus_W": "B_alloc - A_common (derived)",
                                "load_W": [pd_lo, pd_hi], "eta": eta_d, "status": "PRELIMINARY"})
        else:
            steady_rows.append({"component": c, "kind": "ALLOCATION" if c == "compressor" else "PARAMETER",
                                "load_W": e["load_W"], "eta_lower": e["eta_lower"], "bus_W": e["bus_W"],
                                "basis": e["basis"], "status": e["status"]})

    margin_rows = [
        {"id": "MG-1", "item": "RFP requirement", "value_W": R, "basis": "requirement", "note": "strict '<'"},
        {"id": "MG-2", "item": "A5 bus-power design allocation", "value_W": B, "basis": "allocation"},
        {"id": "MG-3", "item": "allocation-to-requirement margin", "value_W": [sig(R - B[1]), sig(R - B[0])],
         "basis": "derived"},
        {"id": "MG-4", "item": "common-auxiliary screening envelope A_common (steady; excl. thermal_control and "
         "atmospheric valve)", "value_W": {"envelope_high": known_hi, "permanent_magnet_keeper_off": known_hi_pm_off},
         "basis": "derived from analog envelopes"},
        {"id": "MG-5", "item": "discharge bus draw available with the reserved slot empty (B - A_common)",
         "value_W": {k: [d["discharge_bus_W_max"] for d in v] for k, v in dalloc.items()}, "basis": "derived"},
        {"id": "MG-6", "item": "hall_discharge load ALLOCATION (upper bound) = eta_d x MG-5",
         "value_W": {k: [d["P_d_load_W_max"] for d in v] for k, v in dalloc.items()}, "basis": "allocation"},
        {"id": "MG-7", "item": "discharge-supply conversion loss at MG-5 (inside P_bus)",
         "value_W": {k: [d["discharge_supply_loss_W"] for d in v] for k, v in dalloc.items()}, "basis": "derived"},
    ]

    headroom = {
        "definition": "reserved pre-ionizer slot (rf_source; alternate ecr_source + ecr_magnet): the bus power a "
                      "contingency module would have to fit. f = discharge bus draw / B_alloc (unknown; A7 blocker 2 "
                      "is measured by H-1 Phase 1).",
        "readings": {
            "R-a_inside_allocation": "H_a(f) = B_alloc x (1 - f) - A_common - A_th - P_air_valve",
            "R-b_inside_requirement": "H_b(f) = 1500 W - f x B_alloc - A_common - A_th - P_air_valve  (the module may "
                                      "use the allocation-to-requirement margin)",
            "which_reading": "owner decision (OQ-H24-02); this lane does not choose",
        },
        "module_fit_conditions_necessary": [
            "P_bus[rf_source] (+ its share of any other booked term) <= H",
            f"P_bus[ecr_source] + P_bus[ecr_magnet] <= H, where P_bus[ecr_source] >= P_delivered x "
            f"{x['ecr_stage_min']} (stage-only lower bound, {x['ecr_stage_min_id']}; AUX ecr_source.bus_draw."
            "bus_W_per_W_load_at_least_for_stage_technology)",
            f"P_bus[source] >= eps_floor x I_src with eps_floor = {x['eps_n2']} W/A (N2 feed), {x['eps_xe']} W/A (Xe feed) "
            "(AUX lower bound; air mixture TBD)",
            "the module's own housekeeping/standby draw is booked under housekeeping (v1 limitation) and must also fit",
        ],
        "chain_factor_context_not_bounds": {
            "rf_source_analog_range": f"P_bus[rf_source] / P_delivered in {x['rf_bpw']} from analog chain efficiencies "
                                      "(RF-NEWORBIT25 nominal 0.92, RF-VOLKMAR18 0.60-0.70; AUX rf_source.bus_draw."
                                      "bus_W_per_W_load): an ANALOG RANGE, not a bound",
            "ecr_source_reference_chain": f"{x['ecr_bpw']} bus W per delivered W for the Hayabusa TWTA reference chain "
                                          "(EC-HAYABUSA-TWTA): a REFERENCE value, neither an upper nor a lower bound "
                                          "(AUX: 'the ABEP chain may be higher or lower')",
            "ecr_source_stage_technology": {k: sig(v) for k, v in sorted(x["ecr_stage"].items())},
        },
        "no_conclusion": "whether an RF or ECR module fits is NOT concluded: the required source power and the "
                         "discharge share f are unknown until H-1 Phase 1; no architecture is selected or eliminated",
        "zero_headroom_share": f_zero,
        "grid_axes": {"f": fgrid, "A_common_W": [sig(a) for a in agrid],
                      "note": "sweep axes (parameters), not predictions; A_common = H24-23 envelope marked"},
        "tabulated_values_are_upper_bounds": "compact_at_envelope, full_grid and zero_headroom_share are evaluated "
                                             "with A_th = P_air_valve = 0 (PENDING H2-5 / H2-3); every tabulated "
                                             "headroom and zero-headroom share is therefore an UPPER BOUND",
        "compact_at_envelope": compact,
        "full_grid": head,
    }

    # ---------------------------------------------------------------- architecture options, grounding, H-1 vs flight
    ppu_options = {
        "discharge_supply": [
            {"id": "DS-A", "topology": "LCC resonant converter, 28 V-class input, 200-500 V out, <= 1 kW",
             "analog": "NASA SSEP sub-kW PPU breadboard (Rhodes 2024)", "evidence": "measured efficiency (EC HD-RH24-*)",
             "gap": "the allocation needs up to ~" + str(round(pd_hi)) + " W output: inside the measured <= 1 kW span",
             "representativeness": "FLIGHT-REPRESENTATIVE"},
            {"id": "DS-B", "topology": NIKRANT22["discharge_topology"] + ", 24-34 V input, up to 1000 W at 200-400 V",
             "analog": "Northrop Grumman 1 kW string PPU (Nikrant 2022 p. 4)", "evidence": "topology and rating only",
             "representativeness": "FLIGHT-REPRESENTATIVE"},
            {"id": "DS-C", "topology": "two-bus PPU (discharge from a higher-voltage bus)", "analog":
             "Pinero 2015 (BUS_POWER_BOUNDARY Sec. 2, E2)", "evidence": "not transferable to a 28 V < 1.5 kW PPU",
             "representativeness": "FLIGHT-REPRESENTATIVE"}],
        "magnet_supply": [
            {"id": "MS-A", "topology": "separate current-controlled supply per coil (isolation stage + buck post-regulator)",
             "analog": "Osuga 2005 Sec. IV.C", "note": "allows the HW-MC-02 per-coil current record; PREFERRED for H-1 "
             "identity with flight (PROPOSED)"},
            {"id": "MS-B", "topology": "shared two-switch-forward design with the heater supply", "analog":
             "Rhodes 2024 slide 3 (via EC HM-SUPPLY-EFF)"},
            {"id": "MS-C", "topology": "coil in series with the discharge (no magnet supply)", "note": "booked under "
             "hall_magnet as coil drop x I_d (boundary Sec. 3); couples B to I_d, conflicts with independent B control "
             "in the H-1 sweeps (HW-MC-02); NOT PROPOSED for H-1"},
            {"id": "MS-D", "topology": "permanent-magnet circuit (0 W, efficiency 1)", "status": pend("H2-1")}],
        "cathode_supplies": [
            {"id": "CS-A", "topology": "combined heater-ignitor-keeper supply", "analog": "Nikrant 2022 p. 4",
             "note": "heater and keeper overlap in SU-2..SU-4, so a combined unit must deliver both at once"},
            {"id": "CS-B", "topology": "separate keeper (current-regulated, ignition >= 150 V) and heater (current-"
             "regulated) supplies", "analog": "Osuga 2005 Table 1 PC2/PC3; Rhodes 2024 slide 3 (flyback keeper)"}],
        "shared_vs_separate": "PROPOSED for the flight reference: separate discharge supply (DS-A class); separate "
                              "per-coil magnet supplies (MS-A) unless H2-1 selects permanent magnets (MS-D); cathode "
                              "supplies CS-A or CS-B open until C-1 selection (H2-2); valve drivers (PFCV + atmospheric "
                              "metering valve) and housekeeping on an auxiliary supply; a reserved DC output port "
                              "(interface only, no installed converter) for the pre-ionizer slot sized to the PMI ICD. "
                              "Owner decision OQ-H24-03.",
        "reserved_slot_port": {"baseline_flight_hardware": False,
                               "requirement": "A5 reserved_interface: electrical ICD defined now so fitting RF after "
                                              "H-1 needs no thruster redesign; the common interface is not RF-specific "
                                              "(A6 common_interface_rule)",
                               "status": pend("PMI", "electrical power boundary")},
        "sequencer": "start-up/stop/failure-recovery sequencing in the PPU controller (analog: Osuga 2009 " +
                     OSUGA09["sequencer_locator"] + "; Nikrant 2022 p. 4 software sequencing)",
        "legacy_model_provenance": {"file": "abep_sim/ppu.py", "introduced": "seed commit 6483358",
                                    "finding": "every numeric default (P_fixed_W, k_cond, k_sw, kg_per_kW, m_base_kg, "
                                               "controller_W 8 W, sensors_W 4 W, V_bus 28 V, the clamp [0.3, 0.985]) "
                                               "is unsourced (evidence class assumed; BUS_POWER_BOUNDARY Sec. 6 finding "
                                               "8); NO value is taken from it; only its converter taxonomy (anode, "
                                               "magnet, keeper, heater, motor, aux, rf_amp, hv_mw) is mapped onto the "
                                               "boundary components"},
    }
    grounding = {
        "flight_reference_PROPOSED": [
            "all PPU secondary outputs isolated (floating) from the primary bus (Osuga 2005/2009 analogs, H24-40)",
            "discharge supply between anode and cathode common; heater and keeper supplies referenced to cathode common",
            "cathode common tied to the thruster body / spacecraft structure through a defined bleed/clamp impedance "
            "(value TBD) -- " + pend("H2-2", "cathode-common topology and return path"),
            "magnet coil supplies isolated; coils insulated from the body (HW-MC-11)",
            "pre-ionizer slot: RF/microwave returns separated from the discharge return (HW-ELEC-03); module body "
            "potential per HWQ-07 -- " + pend("PMI"),
        ],
        "h1_test_article": [
            "HW-ELEC-01: discharge supply between anode and cathode common; the thruster floats; the same topology, "
            "grounding and routing in every arm",
            "HW-C1-05 / INS-02: cathode-to-ground and anode-to-ground potentials recorded at every reading",
            "cathode common to H-1 body / magnetic circuit with the thruster floating from facility ground -- "
            + pend("H2-2", "E1 vs E3 (bleed/clamp) choice"),
            "HW-ELEC-03: DUMMY_LOAD_PICKUP control in S1a for any generator",
        ],
        "status": pend("H2-2", "return path"),
        "representativeness": "flight reference FLIGHT-REPRESENTATIVE; facility-ground bond GROUND/FACILITY-ONLY",
    }
    h1_vs_flight = {
        "distinction": [
            {"item": "flight PPU (discharge, magnet, keeper, heater, valve drivers, housekeeping, reserved port)",
             "representativeness": "FLIGHT-REPRESENTATIVE", "role": "defines the ledger efficiencies eta_c"},
            {"item": "H-1 laboratory supplies (PS-C) with load-plane metering", "representativeness":
             "GROUND/FACILITY-ONLY", "role": "deliver and meter the load-plane powers; their own losses never enter P_bus"},
            {"item": "INS-02 metering channels and their calibration", "representativeness": "H-1 TEST-ARTICLE-ONLY",
             "role": "measure P_load,c per component"},
            {"item": "flight-representative breadboard discharge supply (optional, PROPOSED)", "representativeness":
             "FLIGHT-REPRESENTATIVE", "role": "replaces an analog eta_d by a measured one at the Phase-1 load points"},
        ],
        "P_bus_reconstruction": {
            "equation": "P_bus,v1 = sum_{c in REQUIRED_COMPONENTS[arm], metered} P_load,c(measured at the load plane) / "
                        "eta_c(pre-registered ledger efficiency at that operating point) + sum_{c unmetered} P_bus,c "
                        "(LOCK-1 ledger input)",
            "metered_in_lab": ["hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater",
                               "rf_source (HW-RF)", "ecr_source + ecr_magnet (HW-ECR)"],
            "unmetered_ledger_inputs": ["compressor (upstream ICD; D-11-A PARTIAL_BOUNDARY until it exists)",
                                        "flow_control (flight valve drivers; the lab MFCs are not flight loads)",
                                        "thermal_control (H2-5)", "housekeeping (flight controller + sensors)"],
            "eta_source": "pre-registered at LOCK-1 (ledger inputs lock1_inputs[3]) from analog evidence (H24-05..H24-15) "
                          "or, if available before LOCK-2, from a measured flight-representative breadboard at the "
                          "Phase-1 load points; frozen before any score-bearing run",
            "never": ["lab-supply wall-plug or AC input power", "discharge-only power", "absorbed RF/ECR power",
                      "efficiencies tuned after seeing Phase-1 data"],
            "uncertainty": "u(P_bus)^2 = sum_c (P_load,c/eta_c)^2 [u_rel(P_load,c)^2 + u_rel(eta_c)^2]; the eta_c "
                           "uncertainty is a conditioning input reported separately from the INS-02 metering "
                           "uncertainty (I-U-ABS-P covers metering only)",
            "labels": "PARTIAL_BOUNDARY (no compressor term) vs V1 basis (compressor from the ICD) per D-11-A; "
                      "T/P_bus is reported on both labels, never mixed",
            "lab_dc_input_metering": "kept as supply-efficiency evidence only (INS-02, package reconciliation D-10)",
            "sources": [src("INS", "INS-02 principle and feasibility"), src("L1", "decisions D-11 (D-11-A PROPOSED)"),
                        src("HW", "requirements HW-ENV-05")],
        },
    }

    # ---------------------------------------------------------------- A7 H2 sections
    interface_demands = [
        {"from": "H2-1", "to": "H2-4", "quantity": "coil NI, coil count, R(T) hot/cold, P_mag at setpoint", "value": None,
         "units": "A-turn / ohm / W", "status": pend("H2-1")},
        {"from": "H2-4", "to": "H2-1", "quantity": "magnet supply envelope offered (current control, per coil)",
         "value": {"bus_W_max_envelope": mag_bus_hi, "load_W_envelope": env["hall_magnet"]["load_W"]},
         "units": "W", "status": "PRELIMINARY"},
        {"from": "H2-2", "to": "H2-4", "quantity": "C-1 heater V/I/P and preheat duration; keeper ignition voltage and "
         "current; steady keeper policy; self-heating discharge current; cathode-common return path",
         "value": None, "units": "V / A / W / s", "status": pend("H2-2")},
        {"from": "H2-4", "to": "H2-2", "quantity": "heater / keeper supply capability offered",
         "value": {"heater_W": [heat_bracket[0], heat_bracket[1]], "keeper_ignition_V": ">= 150 V DC (300 V ramp "
                   "option; pulse 300-600 V option)", "keeper_I_A": [o["keeper"]["I_A"][0], x["jpl_kI"]["value"]],
                   "keeper_steady_V_compliance_V_min": KEEPER_V_HI, "keeper_P_out_W_min": keep_load_hi,
                   "steady_keeper_bus_W_envelope": env["cathode_keeper"]["bus_W"]}, "units": "W / V / A",
         "status": "PRELIMINARY"},
        {"from": "H2-3", "to": "H2-4", "quantity": "valve count and coil power (PFCVs, atmospheric metering valve); "
         "compressor motor-drive bus voltage, steady and start-up input power", "value": None, "units": "W / V",
         "status": pend("H2-3")},
        {"from": "H2-4", "to": "H2-3", "quantity": "compressor bus-draw screening ceiling (PROPOSED, OD-C2 open)",
         "value": sig(comp_bus), "units": "W", "status": "PRELIMINARY"},
        {"from": "H2-4", "to": "H2-3", "quantity": "minimum delivered anode flow for the thrust allocation from the "
         "jet-power bound (efficiency 1): CONDITIONAL on the auxiliary envelope at the H24-24 allocation; the weakest "
         "floor (only the known lower auxiliary term booked) is given separately",
         "value": {"conditional_on_A_common_envelope": {
                       "15_mN": sorted(j["mdot_min_mg_s"] for j in jet if j["T_mN"] == 15.0 and j["case"] == "envelope"),
                       "22_mN": sorted(j["mdot_min_mg_s"] for j in jet if j["T_mN"] == 22.0 and j["case"] == "envelope")},
                   "floor_at_known_lower_aux": {
                       "P_d_W": pd_abs,
                       "15_mN": [j["mdot_min_mg_s"] for j in jet if j["T_mN"] == 15.0 and j["case"] == "known_lower_aux"],
                       "22_mN": [j["mdot_min_mg_s"] for j in jet if j["T_mN"] == 22.0 and j["case"] == "known_lower_aux"]}},
         "units": "mg/s", "status": "PRELIMINARY"},
        {"from": "H2-4", "to": "H2-5", "quantity": "PPU steady dissipation = sum P_loss + housekeeping load",
         "value": {"discharge_supply_loss_W": [min(d["discharge_supply_loss_W"][0] for v in dalloc.values() for d in v),
                                               max(d["discharge_supply_loss_W"][1] for v in dalloc.values() for d in v)],
                   "aux_supply_loss_W_envelope": sig((mag_bus_hi - mag_load_hi) + (env["cathode_keeper"]["bus_W"][1] -
                                                      keep_load_hi) + (pfcv_bus_hi - pfcv[1])),
                   "housekeeping_W_envelope": sig(hk_bus_hi)}, "units": "W", "status": "PRELIMINARY"},
        {"from": "H2-5", "to": "H2-4", "quantity": "thermal_control heater load per mode (incl. PPU heaters)",
         "value": None, "units": "W", "status": pend("H2-5")},
        {"from": "H2-6", "to": "H2-4", "quantity": "flight sensor and diagnostics power (housekeeping)", "value": None,
         "units": "W", "status": pend("H2-6")},
        {"from": "H2-4", "to": "H2-6", "quantity": "INS-02 channel list with V/I ranges per component",
         "value": [{"component": r["component"], "V": r["V_range_V"], "I": r["I_range_A"]} for r in load_list[:5]],
         "units": "V / A", "status": "PRELIMINARY"},
        {"from": "H2-4", "to": "H2-7", "quantity": "PPU mass (analog only) and bus harness current",
         "value": {"analog_ppu_mass_kg": NIKRANT22["ppu_mass_kg"], "I_bus_A": [min(i["I_bus_A"] for i in ibus),
                                                                                max(i["I_bus_A"] for i in ibus)]},
         "units": "kg / A", "status": "PRELIMINARY"},
        {"from": "H2-4", "to": "fo_preionizer_module_icd", "quantity": "electrical power boundary of the reserved slot: "
         "headroom function H(f), DC-fed generator input metered, separate RF/microwave return",
         "value": {"headroom_function": "H_a(f) = B_alloc (1 - f) - A_common - A_th - P_air_valve; H_b(f) = 1500 W - "
                                        "f B_alloc - A_common - A_th - P_air_valve",
                   "f_at_zero_headroom_at_envelope": f_zero}, "units": "W / -",
         "status": pend("PMI", "PMI-xx electrical items")},
        {"from": "H2-4", "to": "fo_xe_system_ledger", "quantity": "start-up phase durations feeding t_startup / "
         "t_transition (symbolic)", "value": {"preheat_analogs": {"SITAEL_HC1_pairs": hc1_pairs, "JPL_1p5cm_s": jpl_t}},
         "units": "s", "status": pend("XE")},
        {"from": "H2-4", "to": "fo_phase1_prereg_framework", "quantity": "P_bus reconstruction rule for T/P_bus "
         "(load-plane metering / pre-registered eta_c; PARTIAL vs V1 labels)", "value": "h1_vs_flight."
         "P_bus_reconstruction", "units": "-", "status": pend("P1-PREG")},
        {"from": "H2-4", "to": "fo_subsystem_maturity_matrix", "quantity": "PPU/power distribution row sub-allocation "
         "and proposed state", "value": "m16_rows", "units": "-", "status": pend("M16")},
        {"from": "H2-4", "to": "PS-C", "quantity": "H-1 laboratory supply ratings", "value": "h3_procurement_inputs",
         "units": "-", "status": "PRELIMINARY"},
        {"from": "H2-4", "to": "H-1", "quantity": "anode sense lead and isolation rated to the discharge voltage",
         "value": [min(vd_all), max(vd_all)], "units": "V", "status": "PRELIMINARY"},
    ]

    hic = {
        "verdict": "none found",
        "checks": [
            {"id": "HI-01", "check": "A5 allocation below the requirement", "result": f"{B[1]:g} W < {R:g} W: consistent",
             "evidence_class": "assumed (owner allocation vs RFP)", "finding": "none"},
            {"id": "HI-02", "check": "screening auxiliary envelope below the allocation", "result":
             f"A_common envelope {known_hi} W (excl. thermal_control, atmospheric valve) < {B[0]:g} W", "evidence_class":
             "model-derived from analog envelopes", "finding": "none"},
            {"id": "HI-03", "check": "discharge allocation vs jet-power necessary bound P_d >= T^2/(2 mdot)",
             "result": "delivered flow must exceed " + ", ".join(f"{j['mdot_min_mg_s']} mg/s ({j['T_mN']:g} mN at "
                                                                 f"{j['P_d_alloc_W']} W, {j['case']})" for j in jet
                                                                 if j["T_mN"] in x["T_alloc_mN"]) +
                       "; the 'envelope' values are conditional on the A_common screening envelope, the "
                       "'known_lower_aux' values are the weakest floor inside B_alloc" +
                       "; the candidate valve-flow bracket 0.030-3.14 mg/s (compressor_downselect, A3 candidate "
                       "range) straddles these values", "evidence_class": "model-derived (energy conservation)",
             "finding": "none at the architecture level: a constraint on the delivered flow handed to H2-3 / feed-state "
                        "closure (it applies identically to hall_only, rf_hall and ecr_hall)"},
            {"id": "HI-04", "check": "start-up overlap known terms below 1500 W", "result": f"PK-1 known upper {s4} W; "
             f"{sig(R - s4)} W left for the discharge ignition transient", "evidence_class": "model-derived from analog "
             "brackets", "finding": "none; D_ign TBD (S1)"},
            {"id": "HI-05", "check": "bus input current", "result": f"up to {max(i['I_bus_A'] for i in ibus)} A at 24 V",
             "evidence_class": "model-derived", "finding": "none; harness/connector sizing input to H2-7"},
            {"id": "HI-06", "check": "steady heater/keeper off requires cathode self-heating", "result":
             f"allocation-derived I_d {id_table[-1]['I_d_A_at_P_d_alloc_max'][0]}-{id_table[0]['I_d_A_at_P_d_alloc_max'][1]} A; "
             f"a JPL 1.5-cm LaB6 cathode ran stably without the keeper only above {x['jpl_imin']['value']} A "
             "(different class)",
             "evidence_class": "measured (analog cathode)", "finding": "none: the keeper-on case is inside the envelope "
             "(H24-17); a steady heater would be a new term -> condition handed to H2-2 (C-1 sized for self-heating at "
             "the allocation current)"},
            {"id": "HI-07", "check": "discharge-supply output power inside the analog measured span", "result":
             f"P_d allocation <= {pd_hi} W vs measured 200-1000 W (Rhodes)", "evidence_class": "digitized",
             "finding": "none"},
        ],
        "not_checked": ["compressor input power (H2-3)", "thermal_control (H2-5)", "flight PPU mass and thermal "
                        "rejection closure (H2-7, H2-5)", "the reserved-slot source power (unknown until H-1 Phase 1)"],
    }
    blockers = [
        {"blocker": 1, "touched": False, "how": "none: sustainment is measured by H-1 Phase 1; this lane only fixes how "
         "P_bus is reconstructed at each point"},
        {"blocker": 2, "touched": True, "how": "provides the reserved-slot headroom H(f) as a function of the unknown "
         "discharge share, the full-bus accounting rule (PPU losses inside P_bus) and the P_bus reconstruction for "
         "T/P_bus; draws no conclusion on RF/ECR benefit"},
        {"blocker": 3, "touched": True, "how": "cathode heater/keeper power terms and start-up phase durations "
         "(t_startup, t_transition inputs to the Xe ledger); no Xe mass is set"},
    ]
    m16 = [
        {"subsystem": "PPU/power distribution", "a5_group": "support", "m16_row_id": pend("M16", "row id assigned by "
         "the M16 lane"), "matured_by_this_lane": "component sub-allocation of the A5 P_bus allocation, converter "
         "efficiency parameters, bus profiles, margin table, supply topology options, grounding, H-1 vs flight P_bus "
         "reconstruction", "proposed_state": "RUNNING", "blocking_item": "n/a (not BLOCKED)",
         "rollup": "n/a (not BLOCKED)",
         "note": "addresses the missing component sub-allocation of the A5 bus allocation (LOCK-1 lock1_inputs[2], [3] TBD) with a PROPOSED "
                 "sub-allocation; H-1 is not blocked by the flight PPU (laboratory supplies, PS-C)"},
        {"subsystem": "control/FDIR", "a5_group": "support", "m16_row_id": pend("M16"),
         "matured_by_this_lane": "start-up / transition / shutdown sequence and sequencing constraint SEQ-1",
         "proposed_state": "BLOCKED", "blocking_item": "C-1 selection: heater power and preheat duration, keeper "
         "ignition voltage/current and the steady keeper policy (" + LANES["H2-2"] + ")",
         "rollup": "hardware-definition blocker"},
    ]
    for r in m16:
        need(r["proposed_state"] in M16_STATES, "m16 state")
        if r["proposed_state"] == "BLOCKED":
            need(isinstance(r["blocking_item"], str) and r["rollup"] in ROLLUPS, "BLOCKED row needs one item + rollup")

    h3 = [
        {"id": "H3-PPU-01", "item": "H-1 laboratory discharge supply", "representativeness": "GROUND/FACILITY-ONLY",
         "spec_level_to_order": {"output_V": [0, max(vd_all)], "output_I_A_min_rating": x["id_bound"],
                                 "note": "floating output; programmable current limit and ramp; arc/extinction "
                                         "recovery; transient margin TBD (S1); V_d rating per HWQ-03"},
         "reference": "catalog data as reference only; no supplier contact", "long_lead": False},
        {"id": "H3-PPU-02", "item": "H-1 magnet supplies (one per coil, current control, remote sense)",
         "representativeness": "GROUND/FACILITY-ONLY", "spec_level_to_order": pend("H2-1", "coil V/I"),
         "long_lead": False},
        {"id": "H3-PPU-03", "item": "H-1 keeper supply (>= 150 V open circuit ignition; current-regulated 0.5-2 A class; "
         "steady compliance >= 35 V, >= 60 W output per H24-41) "
         "and heater supply (current-regulated; up to ~305 W, current per C-1)", "representativeness":
         "GROUND/FACILITY-ONLY", "spec_level_to_order": pend("H2-2", "C-1 selection"), "long_lead": False},
        {"id": "H3-PPU-04", "item": "INS-02 bus-power metering (4-wire V, calibrated shunts / zero-flux CTs, "
         "simultaneous sampling) per boundary component", "representativeness": "H-1 TEST-ARTICLE-ONLY",
         "spec_level_to_order": "per-channel 0.50 % repeatability target (INS-02, PROPOSED); ranges from load_list",
         "long_lead": False},
        {"id": "H3-PPU-05", "item": "flight-representative breadboard discharge supply (28 V class, <= 1 kW, 180-350 V) "
         "for measured eta_d at Phase-1 load points (PROPOSED)", "representativeness": "FLIGHT-REPRESENTATIVE",
         "spec_level_to_order": "performance specification (input 24-34 V, output per H24-25/H24-26, efficiency "
                                "measurement method stated)", "long_lead": True,
         "reference": "Rhodes 2024 / Nikrant 2022 as published analogs only"},
        {"id": "H3-PPU-06", "item": "rad-tolerant PPU parts for a flight PPU", "representativeness":
         "FLIGHT-REPRESENTATIVE", "spec_level_to_order": "TBD - requires the redundancy policy (H24-35) and bus "
         "voltage (H24-04)", "long_lead": True},
    ]
    h4 = [
        {"closes": "H24-05 / H24-07..H24-11", "stage": "S1a", "measure": "each lab supply DC input vs load-plane "
         "output at the operating points (supply-efficiency evidence only); optional breadboard eta_d (H3-PPU-05)"},
        {"closes": "H24-38", "stage": "S1a", "measure": "INS-02 channel calibration against a traceable DC standard; "
         "DUMMY_LOAD_PICKUP control"},
        {"closes": "H24-18, H24-19, H24-28..H24-31", "stage": "S1a/S1", "measure": "C-1 heater V/I/P and preheat time; "
         "keeper ignition voltage and current; energy per start"},
        {"closes": "H24-16, H24-32", "stage": "S1", "measure": "coil current, voltage and hot-spot temperature -> "
         "P_mag(T) (HW-MC-14)"},
        {"closes": "PK-1 D_ign, IR-2, H24-27 transient margin", "stage": "S1", "measure": "discharge ignition and "
         "extinction current/voltage transients (time-resolved)"},
        {"closes": "H24-17, HI-06", "stage": "S1b / Phase 1", "measure": "keeper need at the lowest discharge current "
         "of the sweep (keeper on/off, V_cg)"},
        {"closes": "H24-24 (allocation check), headroom f", "stage": "Phase 1", "measure": "V_d x I_d at every point "
         "(measured hall_discharge load) and P_bus reconstructed per h1_vs_flight (PARTIAL and V1 labels)"},
        {"closes": "H24-21", "stage": "compressor bench (H2-3)", "measure": "compressor electrical input power, "
         "steady and start-up (compressor_downselect T-4)"},
    ]
    milestone = {
        "A": "supported: conditional statement 'the A5 reference closes its bus allocation provided the discharge "
             "share f and the measured auxiliaries satisfy f x B + A_common + A_th + P_air_valve <= B_alloc (and the "
             "reserved slot, if fitted, <= H(f))'",
        "B": "not reached: needs measured V_d x I_d (H-1 Phase 1), measured supply efficiencies at the load points, "
             "compressor and thermal_control loads, and the owner reading of the 1.5 kW scope",
        "C": "not reached: needs a flight PPU design (redundancy, mass, thermal, sequencing, FDIR) integrated with "
             "mission closure on bus_power_boundary_v1",
    }
    owner_q = [
        {"id": "OQ-H24-01", "question": "Does the RFP '< 1.5 kW' apply at bus_power_boundary_v1 and to start-up "
         "transients (H24-37)?"},
        {"id": "OQ-H24-02", "question": "Must a contingency pre-ionizer module fit inside the A5 allocation (reading "
         "R-a) or may it use the allocation-to-requirement margin (reading R-b)?"},
        {"id": "OQ-H24-03", "question": "Adopt the PROPOSED supply partition (separate discharge, per-coil magnet, "
         "cathode CS-A/CS-B after C-1, auxiliary valve/housekeeping, reserved DC port)?"},
        {"id": "OQ-H24-04", "question": "Spacecraft bus voltage (28 V class vs regulated 100 V) and redundancy policy "
         "(H24-04, H24-35)."},
        {"id": "OQ-H24-05", "question": "Adopt sequencing constraint SEQ-1 (heater off before compressor spin-up and "
         "before any pre-ionizer seed)?"},
        {"id": "OQ-H24-06", "question": "Procure a flight-representative breadboard discharge supply (H3-PPU-05) so "
         "that eta_d at the Phase-1 load points is measured before LOCK-2?"},
    ]

    return {
        "schema": "h2_lane_deliverable_v1",
        "id": VERSION,
        "lane": "H2-4",
        "follow_on": "fo_h2_4_ppu_bus",
        "trigger": "T_H2_4_PPU_BUS",
        "owner_disposition": "A7 (H2 hardware wave)",
        "status": "PRELIMINARY_DRAFT_FOR_OWNER",
        "base_commit": BASE_COMMIT,
        "date": DATE,
        "generated_by": SCRIPT_REL,
        "regenerate": f"python {SCRIPT_REL}  (check: --check)",
        "boundary_version": BOUNDARY_VERSION,
        "architectures": list(ARCHS),
        "scope": "H2 hardware design / preliminary-sizing lane (A7 h2_scope): PPU and bus allocation for configuration "
                 "item PS-C on bus_power_boundary_v1. Not an architecture-selection lane.",
        "what_this_is_not": [
            "not a Hall performance prediction: hall_discharge is an ALLOCATION derived from the A5 P_bus allocation",
            "not an architecture selection: no winner among hall_only / rf_hall / ecr_hall, no elimination",
            "not a use of any Hall transport closure (credible set empty), of abep_sim/plasma_devices.py or of the "
            "withdrawn v1.2-v1.6 numbers",
            "not a change of Bundle 1 (stays NO_BASELINE_YET) or of any A6 not_authorized item",
            "not a use of P5 calibration-nuisance items as design variables",
        ],
        "decision_pins": [{"key": k, "path": INPUTS[k][0], "sha256": INPUTS[k][1], "role": INPUTS[k][2]}
                          for k in ("A5", "A6", "A7", "G0")],
        "pinned_inputs": [{"key": k, "path": v[0], "sha256": v[1], "role": v[2]} for k, v in INPUTS.items()
                          if k not in ("A5", "A6", "A7", "G0")],
        "external_sources": EXTERNAL,
        "external_values": {"S-OSUGA05": OSUGA05_TABLE1, "S-OSUGA09": OSUGA09, "S-NIKRANT22": NIKRANT22},
        "parallel_lanes": LANES,
        "design_parameters": params,
        "load_list": load_list,
        "converter_efficiency_parameters": [p for p in params if p["id"] in
                                            ("H24-05", "H24-06", "H24-07", "H24-08", "H24-09", "H24-10", "H24-11",
                                             "H24-12", "H24-13", "H24-14", "H24-15")],
        "bus_profiles": {
            "STEADY": {"mode": "atmospheric Hall + Xe cathode (nominal), hall_only baseline, reserved slot empty",
                       "rows": steady_rows, "A_common_envelope_W": {"high": known_hi, "pm_keeper_off": known_hi_pm_off,
                                                                    "known_lower": known_lo},
                       "discharge_allocation": dalloc, "I_d_at_allocation": id_table,
                       "open_terms": ["A_th (thermal_control, H2-5)", "P_air_valve (atmospheric metering valve, H2-3)"],
                       "architectures_note": "rf_hall / ecr_hall use the same common rows (loads may differ per arm, the "
                                             "component set may not) plus rf_source, or ecr_source + ecr_magnet, whose "
                                             "bus draw must fit the headroom H(f) of margin_table.headroom"},
            "STARTUP": {"sequence_basis": "A5 operating_modes.sequence; phase order Goebel & Katz Sec. 7.2.3 via "
                                          "cathode_integration startup_reference; magnet ramp placement PROPOSED",
                        "phases": phases, "other_modes": other_modes},
            "PEAK": {"overlaps": peak, "inrush": inrush,
                     "rule": "H24-37 PROPOSED (owner)", "sequencing_constraint": "H24-36 SEQ-1 PROPOSED"},
        },
        "margin_table": {"rows": margin_rows, "headroom": headroom, "T_over_Pbus_floor_implied_by_allocation": tp_floor,
                         "jet_power_bound": jet, "bus_current": ibus},
        "ppu_architecture_options": ppu_options,
        "grounding": grounding,
        "h1_vs_flight": h1_vs_flight,
        "interface_demands": interface_demands,
        "hard_incompatibility_check": hic,
        "architecture_changing_blockers_touched": blockers,
        "m16_rows": m16,
        "h3_procurement_inputs": h3,
        "h4_test_inputs": h4,
        "milestone_statement": milestone,
        "owner_questions": owner_q,
        "compliance": {
            "allowed_paths": [LANE_DIR + "**", "tests/test_h2_4_ppu_bus.py"],
            "no_hall_closure": True, "no_screening_candidate": True, "no_winner": True,
            "no_archengine_wiring": True, "pins_mutable_governance": False,
            "a6_not_authorized_respected": ["no Xe mass frozen", "no startup/transition/fallback quantity frozen",
                                            "no Phase-1 numeric threshold frozen", "Bundle 1 unchanged"],
        },
    }


# ------------------------------------------------------------------------------------------------ markdown
def _fmt(v):
    if isinstance(v, list) and len(v) == 2 and all(a is None or (isinstance(a, (int, float)) and not isinstance(a, bool))
                                                  for a in v) and any(a is not None for a in v):
        return "–".join("TBD" if a is None else _fmt(a) for a in v)
    if isinstance(v, list):
        return "–".join(_fmt(a) for a in v) if len(v) == 2 and all(isinstance(a, (int, float)) for a in v) \
            else ", ".join(_fmt(a) for a in v)
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_fmt(a)}" for k, a in v.items())
    if v is None:
        return "TBD"
    return str(v).replace("|", "/")


def render_md(d: dict) -> str:
    L = []
    a = L.append
    a("# H2-4 PPU and bus allocation (PS-C) on `bus_power_boundary_v1`")
    a("")
    a(f"<!-- GENERATED by {d['generated_by']} from h2_4_ppu_bus_v1.json; do not edit by hand -->")
    a("")
    a("| item | value |")
    a("|---|---|")
    a(f"| follow-on | `{d['follow_on']}` (trigger `{d['trigger']}`, owner addendum A7) |")
    a(f"| base commit | `{d['base_commit']}` |")
    a(f"| status | {d['status']} |")
    a(f"| regenerate | `{d['regenerate']}` |")
    a(f"| scope | {d['scope']} |")
    a("")
    a("**What this is not.** " + " ".join(f"({i + 1}) {t}." for i, t in enumerate(d["what_this_is_not"])))
    a("")
    a("Decision pins (immutable, sha256): " + "; ".join(f"`{p['path']}` `{p['sha256']}`" for p in d["decision_pins"]))
    a("")
    a("## 1. Design-parameter table")
    a("")
    a("| id | name | value | units | basis | evidence class | status | representativeness | CI | source |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for p in d["design_parameters"]:
        a(f"| {p['id']} | {_fmt(p['name'])} | {_fmt(p['value'])} | {p['units']} | {p['basis']} | {p['evidence_class']} | "
          f"{_fmt(p['status'])} | {p['representativeness']} | {', '.join(p['configuration_items'])} | {_fmt(p['source'])} |")
    a("")
    a("## 2. Load list per bus_power_boundary_v1 component")
    a("")
    a("| component | kind | load [W] | V | I | efficiency param | status |")
    a("|---|---|---|---|---|---|---|")
    for r in d["load_list"]:
        a(f"| `{r['component']}` | {r['kind']} | {_fmt(r['load_W'])} | {_fmt(r['V_range_V'])} | {_fmt(r['I_range_A'])} | "
          f"{_fmt(r['efficiency_parameter'])} | {_fmt(r['status'])} |")
    a("")
    a("`rf_source`, `ecr_source` and `ecr_magnet` are the reserved / alternate pre-ionizer slot (not baseline flight "
      "hardware, A5 reserved_interface). Every row is an ALLOCATION or a PARAMETER; none is a Hall performance prediction.")
    a("")
    s = d["bus_profiles"]["STEADY"]
    a("## 3. Bus profiles")
    a("")
    a("### 3.1 STEADY (atmospheric Hall + Xe cathode, hall_only baseline, reserved slot empty)")
    a("")
    a("| component | kind | load [W] | eta lower | bus draw [W] | status |")
    a("|---|---|---|---|---|---|")
    for r in s["rows"]:
        a(f"| `{r['component']}` | {r['kind']} | {_fmt(r['load_W'])} | {_fmt(r.get('eta_lower', r.get('eta')))} | "
          f"{_fmt(r['bus_W'])} | {_fmt(r['status'])} |")
    a("")
    a(f"Common-auxiliary screening envelope A_common: high {s['A_common_envelope_W']['high']} W; permanent magnet + keeper "
      f"off {s['A_common_envelope_W']['pm_keeper_off']} W (thermal_control and the atmospheric metering valve excluded, "
      "carried symbolically).")
    a("")
    a("| case | B_alloc [W] | A_common [W] | discharge bus draw max [W] | P_d ALLOCATION max [W] | discharge-supply loss [W] |")
    a("|---|---|---|---|---|---|")
    for k, v in s["discharge_allocation"].items():
        for r in v:
            a(f"| {k} | {r['B_alloc_W']:g} | {r['A_common_W']:g} | {r['discharge_bus_W_max']:g} | "
              f"{_fmt(r['P_d_load_W_max'])} | {_fmt(r['discharge_supply_loss_W'])} |")
    a("")
    a("Allocation-derived discharge current (not a prediction): " + "; ".join(
        f"{r['V_d_V']:g} V → {_fmt(r['I_d_A_at_P_d_alloc_max'])} A" for r in s["I_d_at_allocation"]))
    a("")
    a("### 3.2 STARTUP (time-resolved sequence)")
    a("")
    a("| id | A5 mode | phase | components on | duration | known bus upper [W] | open terms |")
    a("|---|---|---|---|---|---|---|")
    for p in d["bus_profiles"]["STARTUP"]["phases"]:
        a(f"| {p['id']} | {p['a5_mode']} | {p['name']} | {', '.join(p['on'])} | {_fmt(p['duration'])} | "
          f"{_fmt(p.get('known_bus_W_upper', p.get('known_aux_bus_W_upper', p.get('profile'))))} | "
          f"{_fmt(p.get('open_terms', ''))} |")
    a("")
    for m in d["bus_profiles"]["STARTUP"]["other_modes"]:
        a(f"- **{m['a5_mode']}**: {m['profile']} ({_fmt(m['status'])})")
    a("")
    a("### 3.3 PEAK (worst simultaneous loads, transients, inrush)")
    a("")
    for p in d["bus_profiles"]["PEAK"]["overlaps"]:
        extra = {k: v for k, v in p.items() if k.startswith("headroom") or k.startswith("known") or k.startswith("extra")}
        a(f"- **{p['id']} {p['name']}**: `{p['expression']}`" + (f"; {_fmt(extra)}" if extra else "") +
          (f". {p['note']}" if p.get("note") else "") + (f" ({_fmt(p['status'])})" if p.get("status") else ""))
    a("")
    for r in d["bus_profiles"]["PEAK"]["inrush"]:
        a(f"- {r['id']} {r['item']}: {r['value']}")
    a("")
    a("## 4. Margin table and reserved-slot headroom")
    a("")
    a("| id | item | value [W] | basis |")
    a("|---|---|---|---|")
    for r in d["margin_table"]["rows"]:
        a(f"| {r['id']} | {r['item']} | {_fmt(r['value_W'])} | {r['basis']} |")
    a("")
    h = d["margin_table"]["headroom"]
    a(h["definition"])
    a("")
    for k, v in h["readings"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("Necessary module-fit conditions: " + " / ".join(h["module_fit_conditions_necessary"]) + ".")
    a("")
    a(f"**{h['no_conclusion']}.**")
    a("")
    a("Headroom at the screening envelope A_common (W), as a function of the discharge bus share f. The table is "
      "evaluated with A_th = P_air_valve = 0 (both PENDING H2-5 / H2-3, carried symbolically in the formulas), so "
      "every tabulated value, and every zero-headroom share below, is an UPPER BOUND on the slot headroom:")
    a("")
    a("| f | " + " | ".join(f"H_a (B={b:g})" for b in (1300.0, 1350.0)) + " | " +
      " | ".join(f"H_b (B={b:g})" for b in (1300.0, 1350.0)) + " |")
    a("|---|---|---|---|---|")
    fs = sorted({r["f_discharge_bus_share"] for r in h["compact_at_envelope"]})
    for f in fs:
        rows = {r["B_alloc_W"]: r for r in h["compact_at_envelope"] if r["f_discharge_bus_share"] == f}
        a(f"| {f:g} | {rows[1300.0]['H_inside_allocation_W']:g} | {rows[1350.0]['H_inside_allocation_W']:g} | "
          f"{rows[1300.0]['H_inside_requirement_W']:g} | {rows[1350.0]['H_inside_requirement_W']:g} |")
    a("")
    a("Negative headroom means no slot budget at that share. The full grid over A_common is in the JSON "
      "(`margin_table.headroom.full_grid`). Share at zero headroom (upper bounds, A_th = P_air_valve = 0): " + "; ".join(
          f"B={z['B_alloc_W']:g} W: f = {z['f_at_zero_headroom_inside_allocation']} (R-a), "
          f"{z['f_at_zero_headroom_inside_requirement']} (R-b)" for z in h["zero_headroom_share"]))
    a("")
    a("Requirement-derived T/P_bus floor implied by the A5 allocations (not a prediction): " + "; ".join(
        f"{t['T_mN']:g} mN at {t['B_W']:g} W → {t['T_over_Pbus_min_mN_per_kW']} mN/kW"
        for t in d["margin_table"]["T_over_Pbus_floor_implied_by_allocation"]))
    a("")
    a("Jet-power necessary bound (efficiency 1): minimum delivered anode flow " + "; ".join(
        f"{j['T_mN']:g} mN @ {j['P_d_alloc_W']:g} W ({j['case']}) → {j['mdot_min_mg_s']} mg/s"
        for j in d["margin_table"]["jet_power_bound"]) + ". 'envelope' values are CONDITIONAL on the A_common "
      "screening envelope; 'known_lower_aux' is the weakest floor (largest P_d compatible with B_alloc when only the "
      "known lower auxiliary term is booked); none is a strict physical floor beyond that.")
    a("")
    a("## 5. PPU architecture options, grounding, H-1 ground supplies vs flight PPU")
    a("")
    o = d["ppu_architecture_options"]
    for grp in ("discharge_supply", "magnet_supply", "cathode_supplies"):
        a(f"**{grp}**")
        a("")
        for it in o[grp]:
            a("- " + f"{it['id']}: {it['topology']}" + "".join(f"; {k}: {_fmt(v)}" for k, v in it.items()
                                                             if k not in ("id", "topology")))
        a("")
    a(f"**Shared vs separate.** {o['shared_vs_separate']}")
    a("")
    a(f"**Reserved slot port.** {_fmt(o['reserved_slot_port'])}")
    a("")
    a(f"**Sequencer.** {o['sequencer']}")
    a("")
    a(f"**abep_sim/ppu.py provenance.** {o['legacy_model_provenance']['finding']}.")
    a("")
    g = d["grounding"]
    a("**Grounding, flight reference (PROPOSED).**")
    a("")
    for t in g["flight_reference_PROPOSED"]:
        a(f"- {t}")
    a("")
    a("**Grounding, H-1 test article.**")
    a("")
    for t in g["h1_test_article"]:
        a(f"- {t}")
    a("")
    hv = d["h1_vs_flight"]
    a("| item | representativeness | role |")
    a("|---|---|---|")
    for r in hv["distinction"]:
        a(f"| {r['item']} | {r['representativeness']} | {r['role']} |")
    a("")
    pr = hv["P_bus_reconstruction"]
    a("**P_bus reconstruction for the Phase-1 T/P_bus quantity.**")
    a("")
    a(f"`{pr['equation']}`")
    a("")
    a(f"- metered in the lab: {', '.join(pr['metered_in_lab'])}")
    a(f"- ledger inputs (unmetered): {', '.join(pr['unmetered_ledger_inputs'])}")
    a(f"- efficiencies: {pr['eta_source']}")
    a(f"- never: {', '.join(pr['never'])}")
    a(f"- uncertainty: {pr['uncertainty']}")
    a(f"- labels: {pr['labels']}")
    a("")
    a("## 6. Interface demands")
    a("")
    a("| from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|")
    for r in d["interface_demands"]:
        a(f"| {r['from']} | {r['to']} | {r['quantity']} | {_fmt(r['value'])} | {r['units']} | {_fmt(r['status'])} |")
    a("")
    a("## 7. Hard-incompatibility check")
    a("")
    hc = d["hard_incompatibility_check"]
    a(f"Verdict: **{hc['verdict']}**.")
    a("")
    a("| id | check | result | evidence class | finding |")
    a("|---|---|---|---|---|")
    for c in hc["checks"]:
        a(f"| {c['id']} | {c['check']} | {_fmt(c['result'])} | {c['evidence_class']} | {c['finding']} |")
    a("")
    a("Not checked here: " + "; ".join(hc["not_checked"]) + ".")
    a("")
    a("## 8. A7 architecture-changing blockers touched")
    a("")
    for b in d["architecture_changing_blockers_touched"]:
        a(f"- blocker {b['blocker']}: {'touched' if b['touched'] else 'not touched'} — {b['how']}")
    a("")
    a("## 9. M16 rows")
    a("")
    a("| subsystem | proposed state | matured by this lane | blocking item | rollup |")
    a("|---|---|---|---|---|")
    for r in d["m16_rows"]:
        a(f"| {r['subsystem']} | {r['proposed_state']} | {r['matured_by_this_lane']} | {_fmt(r['blocking_item'])} | "
          f"{_fmt(r['rollup'])} |")
    a("")
    a("## 10. H3 procurement inputs")
    a("")
    for r in d["h3_procurement_inputs"]:
        a(f"- **{r['id']}** {r['item']} [{r['representativeness']}; long-lead: {r['long_lead']}]: "
          f"{_fmt(r['spec_level_to_order'])}")
    a("")
    a("## 11. H4 test inputs")
    a("")
    a("| closes | stage | measure |")
    a("|---|---|---|")
    for r in d["h4_test_inputs"]:
        a(f"| {r['closes']} | {r['stage']} | {r['measure']} |")
    a("")
    a("## 12. Milestones")
    a("")
    for k, v in d["milestone_statement"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("## 13. Owner questions (thresholds not in the RFP are PROPOSED)")
    a("")
    for q in d["owner_questions"]:
        a(f"- {q['id']}: {q['question']}")
    a("")
    a("## 14. Sources")
    a("")
    for k, v in d["external_sources"].items():
        a(f"- {k}: {v['citation']}. {v['url']} (accessed {v['accessed']}, open; sha256 `{v['sha256_accessed']}`)")
    for p in d["pinned_inputs"]:
        a(f"- `{p['path']}` sha256 `{p['sha256']}` — {p['role']}")
    a("")
    a("Parallel lanes are referenced only as `PENDING <path>`; none is read by the builder or the tests.")
    a("")
    return "\n".join(L)


def dumps(d: dict) -> str:
    return json.dumps(d, indent=1, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs reproduce byte-for-byte")
    args = ap.parse_args(argv)
    d = build(load_inputs())
    js, md = dumps(d), render_md(d)
    if args.check:
        ok = True
        for path, text in ((OUT_JSON, js), (OUT_MD, md)):
            if not os.path.isfile(path) or open(path, encoding="utf-8").read() != text:
                print(f"DRIFT: {os.path.relpath(path, ROOT)}")
                ok = False
        print("OK" if ok else "FAIL")
        return 0 if ok else 1
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(js)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {os.path.relpath(OUT_JSON, ROOT)} and {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
