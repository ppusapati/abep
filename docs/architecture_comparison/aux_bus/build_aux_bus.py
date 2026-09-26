#!/usr/bin/env python3
"""Full auxiliary / DC-bus power comparison of hall_only, rf_hall and ecr_hall on bus_power_boundary_v1.

Follow-on ``fo_aux_bus_comparison`` (trigger ``T_AUX_BUS``; prerequisites lane_20_ppu_magnet, lane_19_cathode_integration,
lane_11_bus_boundary). DRAFT for owner review.

What it does (deterministic, standard library + repository modules, no simulation, nothing wired into archengine):
  * reads the verified input files named in ``INPUTS`` and refuses to run if any is missing or its sha256 differs from
    the pin (no fallback, no substitution);
  * builds, for every architecture x every bus_power_boundary_v1 component x mode (steady, startup), the load-plane
    power, the bus-to-load efficiency, the bus draw and the conversion loss as sourced values, ranges, bounds or TBD,
    each with the input entry ids, the evidence class and the derivation;
  * tries every full ledger with ``abep_sim.arch_boundary.bus_power_ledger`` itself; a ledger is evaluated only if every
    load and efficiency of the architecture is sourced, otherwise it is reported NOT_EVALUABLE with the boundary's own
    refusal message and the blocking inputs;
  * classifies each component of rf_hall - hall_only and ecr_hall - hall_only as common-mode (cancels) or not;
  * writes the RFP < 1.5 kW headroom as a conditional inequality in the unknown Hall discharge load (symbolic);
  * runs the lane-24 hard-gate evaluator (abep_sim.hard_gates.evaluate_all) on the evidence this lane can register
    (none is verdict-bearing), so no elimination can come from this lane except through that evaluator.

Outputs (next to this script): aux_bus_comparison_v1.json (validated against aux_bus_comparison_v1.schema.json) and
AUX_BUS_COMPARISON.md (generated from the JSON).

    python docs/architecture_comparison/aux_bus/build_aux_bus.py            # (re)write the outputs
    python docs/architecture_comparison/aux_bus/build_aux_bus.py --check    # byte-for-byte reproduction check (exit 1 on drift)
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_JSON = os.path.join(HERE, "aux_bus_comparison_v1.json")
OUT_MD = os.path.join(HERE, "AUX_BUS_COMPARISON.md")
SCHEMA_PATH = os.path.join(HERE, "aux_bus_comparison_v1.schema.json")
SCRIPT_REL = "docs/architecture_comparison/aux_bus/build_aux_bus.py"

VERSION = "aux_bus_comparison_v1"
BOUNDARY_VERSION = "bus_power_boundary_v1"
BASE_COMMIT = "d939ef66324b7d1036b2c9bcd5e7674df218342b"
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
MODES = ("steady", "startup")


class AuxBusInputError(RuntimeError):
    """A pinned input is missing, changed, or lacks an entry this build needs (no fallback)."""


# ------------------------------------------------------------------------------------------------ pinned inputs
# key -> (repository-relative path, producing lane id, lane commit, sha256 at the base commit, role)
INPUTS = {
    "boundary_module": ("abep_sim/arch_boundary.py", "lane_11_bus_boundary",
                        "a2a139686dd25ea0f5f4fa908f9d57c25d3746dd",
                        "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae",
                        "bus_power_boundary_v1: component sets and bus_power_ledger (every ledger here)"),
    "boundary_doc": ("docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md", "lane_11_bus_boundary",
                     "a2a139686dd25ea0f5f4fa908f9d57c25d3746dd",
                     "2432edb7e9095fd630585768a62a811140b5230ba035afa3f0fc168636d11ca9",
                     "component load planes, zero-power conventions, v1 standby limitation (Sec. 2), caller rules (Sec. 5)"),
    "magnet_module": ("abep_sim/magnet_power.py", "lane_20_ppu_magnet", "f7c226848d85fedb70c03bae9971be3b2bbde1fe",
                      "adf2905d90b7dd17b59071759d0a62b245fa065b0c3375c74df4e3476b7bb523",
                      "copper resistance-temperature factor [E3] and the B^2 coil-power relation [E5]"),
    "electrical_closure_data": ("docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
                                "lane_20_ppu_magnet", "f7c226848d85fedb70c03bae9971be3b2bbde1fe",
                                "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501",
                                "supply/chain efficiencies and auxiliary load entries by component (entry ids)"),
    "electrical_closure_worked_example": ("docs/architecture_comparison/electrical_closure/worked_example_v1.json",
                                          "lane_20_ppu_magnet", "f7c226848d85fedb70c03bae9971be3b2bbde1fe",
                                          "ae0158e269ada00bfd03bd17c896c509241817b0b89c2edbb5512fe7819d72b3",
                                          "cross-check of the recomputed discharge points and source-chain spreads"),
    "cathode_module": ("abep_sim/cathode_integration.py", "lane_19_cathode_integration",
                       "eff15f85c53244556b1a9a9274fb7ffe80e9fa90",
                       "9c8e776b851c112da89b0621a2e1da0dd128ab647229214b81aed19c3e0561b0",
                       "steady cathode loads and start-up transient functions (start-up phase contract)"),
    "cathode_data": ("docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
                     "lane_19_cathode_integration", "eff15f85c53244556b1a9a9274fb7ffe80e9fa90",
                     "df020bfe3ef87b0fc6f49c56db7e38dc585c4640b5c89dd167d1f18e928dbd6f",
                     "keeper/heater parameters, start-up phase order and variants, PROPOSED start-up peak limit"),
    "cathode_derived": ("docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json",
                        "lane_19_cathode_integration", "eff15f85c53244556b1a9a9274fb7ffe80e9fa90",
                        "a0c8c247d2f87654568da3c01fece2ad562c1ca8e2ba78140813394aed81c125",
                        "heater energy per start"),
    "rf_overlay": ("docs/architecture_comparison/overlays/rf/overlay_rf_v1.json", "fo_rf_breakeven_overlay",
                   "9ef356b536f84e203b87b583b7246e72dcc07d71",
                   "ba739be2fdf431ac33900207cd8365d265456ad7b9d7e6a71e0875524c662359",
                   "rf_source chain evidence and eta_t basis (ion-current basis, <= 1 for a source-free duct)"),
    "ecr_overlay": ("docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json", "fo_ecr_breakeven_overlay",
                    "d22bc6053a64230dd01b8df0e764d884bab722a9",
                    "3ee12e66f94204955f61cbb78d7c5036044cc59a9bc50f675704592bfbfabfcd",
                    "ecr_source chain evidence, ecr_magnet options, ionization-energy floor on source power per ampere"),
    "breakeven_derivation": ("docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md", "lane_28_break_even",
                             "2ad4c463d7a7bd7b983e2de30f8fb34d8cac92fa",
                             "e65c28c040c1fbd9b079d4d4872316441e4f4114f37ff70e79138aab8c134d86",
                             "overhead O and omega definitions (Sec. 4) that the differential terms feed"),
    "interstage_doc": ("docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md", "lane_18_interstage",
                       "870514285c087382b21812c65bd9db196a5a985f",
                       "2a08e8045d1cb61a121e84dc9f7bba268a1ec7b66476057d9093b4e044f6d616",
                       "eta_t definition (charge-current basis)"),
    "hard_gates_module": ("abep_sim/hard_gates.py", "lane_24_hard_gates", "08b9f9bf32a0b34142338b2003f2b2cf02ecaacc",
                          "a36fe3c9065291f0fe5be3f17e179d5b691f00c013f7f8ef299fa89db896dda8",
                          "the only elimination path: evaluate_all(evidence); also the JSON-schema checker"),
    "hard_gate_matrix": ("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json", "lane_24_hard_gates",
                         "08b9f9bf32a0b34142338b2003f2b2cf02ecaacc",
                         "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f",
                         "G2_bus_power criterion (RFP 1500 W as recorded, readings OD4/OD8)"),
    "hard_gate_schema": ("schemas/architecture_comparison/hard_gates_v1.schema.json", "lane_24_hard_gates",
                         "08b9f9bf32a0b34142338b2003f2b2cf02ecaacc",
                         "e5c70c588f3e785720c0d9d01013e5725807b9fd288fa8a1bddf6ba6d86f54ba",
                         "read by hard_gates.evaluate"),
    "transport_ensemble": ("hallthruster_bridge/ensemble/transport_ensemble_v0.json", "project (read-only)", None,
                           "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b",
                           "admitted members for the hard-gate evaluator (credible set empty)"),
    "hall_ensemble_module": ("abep_sim/hall_ensemble.py", "project (read-only)", None,
                             "218f890c8444af1f593396da5051e38d2d093bbb3cb0bc976cc44b01b67df704",
                             "admission guard used by the hard-gate evaluator"),
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_inputs(root: str = ROOT) -> list:
    """Check every pinned input exists with its pinned sha256; raise AuxBusInputError otherwise."""
    problems, table = [], []
    for key in sorted(INPUTS):
        rel, lane, commit, sha, role = INPUTS[key]
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            problems.append(f"{key}: missing input {rel} (lane {lane})")
            continue
        got = _sha256(p)
        if got != sha:
            problems.append(f"{key}: {rel} sha256 {got} != pinned {sha} (lane {lane}); the input changed: "
                            f"re-verify it and re-pin deliberately, never substitute")
        table.append({"key": key, "path": rel, "lane": lane, "lane_commit": commit, "sha256": sha, "role": role})
    if problems:
        raise AuxBusInputError("pinned inputs refused:\n  " + "\n  ".join(problems))
    return table


def _load(key: str, root: str = ROOT):
    with open(os.path.join(root, INPUTS[key][0]), encoding="utf-8") as f:
        return json.load(f)


def _import(modname: str):
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        return importlib.import_module(modname)
    except ImportError as exc:  # lazy resolution with a clear error; never a fallback
        raise AuxBusInputError(f"{modname} could not be imported from {ROOT}: {exc}") from exc


def _sig(x: float, n: int = 6) -> float:
    """Deterministic rounding to n significant digits (reporting only)."""
    return float(f"{x:.{n}g}")


# ------------------------------------------------------------------------------------------------ input accessors
class Inputs:
    def __init__(self, root: str = ROOT):
        self.ec = _load("electrical_closure_data", root)
        self.we = _load("electrical_closure_worked_example", root)
        self.cd = _load("cathode_data", root)
        self.cdd = _load("cathode_derived", root)
        self.rf = _load("rf_overlay", root)
        self.ecr = _load("ecr_overlay", root)
        self.hgm = _load("hard_gate_matrix", root)
        if self.ec.get("boundary_version") != BOUNDARY_VERSION:
            raise AuxBusInputError(f"electrical_closure_data boundary_version {self.ec.get('boundary_version')!r}")

    def entry(self, component: str, eid: str) -> dict:
        try:
            comp = self.ec["components"][component]
        except KeyError:
            raise AuxBusInputError(f"electrical_closure_data has no component {component!r}") from None
        for e in comp["entries"]:
            if e["id"] == eid:
                return e
        raise AuxBusInputError(f"electrical_closure_data[{component}] has no entry {eid!r}")

    def param(self, pid: str) -> dict:
        try:
            return self.cd["parameters"][pid]
        except KeyError:
            raise AuxBusInputError(f"cathode_integration_data has no parameter {pid!r}") from None


def _ref_ec(e: dict) -> dict:
    """Compact evidence reference to a lane-20 entry (values are copied from the input, never retyped)."""
    return {"input": "electrical_closure_data", "id": e["id"], "evidence_class": e["evidence_class"],
            "evidence_level": e["evidence_level"], "source_ids": list(e["source_ids"]), "locator": e["locator"],
            "value": e["value"], "units": e["units"], "uncertainty": e["uncertainty"],
            "chain_stage": e["chain_stage"]}


def _ref_cd(pid: str, p: dict, evidence_class: str) -> dict:
    return {"input": "cathode_data", "id": pid, "evidence_class": evidence_class,
            "evidence_level": p["evidence_level"], "source_ids": [p["source_id"]], "locator": p["locator"],
            "value": p["value"], "units": p["unit"], "uncertainty": p["uncertainty"],
            "quantity_type": p["quantity_type"], "applicability": p["applicability_domain"]}


def _tbd(requires: str, blocking: str, ids=()) -> dict:
    return {"status": "TBD", "requires": requires, "blocking": blocking, "entry_ids": list(ids)}


# ------------------------------------------------------------------------------------------------ component rows
def discharge_efficiency(inp: Inputs) -> dict:
    """Rhodes 2024 slide-11 series (lane 20 HD-RH24-*): range at 28 V in and over all input voltages."""
    comp = inp.ec["components"]["hall_discharge"]
    ids = comp["efficiency_evidence"]
    if not ids:
        raise AuxBusInputError("hall_discharge has no efficiency evidence entries")
    series = {i: inp.entry("hall_discharge", i) for i in ids}
    all_pts = [(i, pt) for i, e in series.items() for pt in e["value"]]
    pts28 = [(i, pt) for i, pt in all_pts if i.endswith("-28Vin")]
    if not pts28:
        raise AuxBusInputError("no 28 V-input discharge-supply series in electrical_closure_data")

    def rng(pts):
        effs = [pt["efficiency"] for _, pt in pts]
        return min(effs), max(effs)

    lo28, hi28 = rng(pts28)
    lo, hi = rng(all_pts)
    rows = []
    for i, pt in sorted(pts28, key=lambda t: (t[0], t[1]["P_out_W"])):
        eta, pl = pt["efficiency"], pt["P_out_W"]
        pb = pl / eta
        rows.append({"series": i, "V_out_V": int(i.split("-")[2].rstrip("V")), "P_load_W": pl, "efficiency": eta,
                     "P_bus_W": _sig(pb), "P_loss_W": _sig(pb - pl),
                     "aux_allowance_below_1500W_W": _sig(1500.0 - pb)})
    return {"ids": list(ids), "eta28": (lo28, hi28), "eta_all": (lo, hi), "points28": rows,
            "P_load_28_range_W": (min(r["P_load_W"] for r in rows), max(r["P_load_W"] for r in rows)),
            "evidence_class": sorted({series[i]["evidence_class"] for i in ids}),
            "evidence_level": sorted({series[i]["evidence_level"] for i in ids}),
            "source_ids": sorted({s for i in ids for s in series[i]["source_ids"]})}


def _per_unit(eta_lo: float, eta_hi: float) -> dict:
    return {"bus_W_per_W_load": [_sig(1.0 / eta_hi), _sig(1.0 / eta_lo)],
            "loss_W_per_W_load": [_sig(1.0 / eta_hi - 1.0), _sig(1.0 / eta_lo - 1.0)],
            "derivation": "P_bus = P_load / eta, P_loss = P_bus - P_load (bus_power_boundary_v1 per-item relation)"}


def build_components(inp: Inputs, mp) -> dict:
    """Per component and mode: load, efficiency, bus draw, loss. Values only from pinned inputs or TBD."""
    E = inp.entry
    comps = {}
    hd = discharge_efficiency(inp)

    # ---- hall_discharge
    hd_eff = {"status": "EVIDENCE_RANGE", "range": [hd["eta28"][0], hd["eta28"][1]],
              "range_all_input_voltages": [hd["eta_all"][0], hd["eta_all"][1]],
              "evidence_class": "digitized", "evidence_level": 3, "entry_ids": hd["ids"],
              "applicability": f"NASA SSEP LCC breadboard discharge supply, 24-34 V in, 200-500 V out, "
                               f"{hd['P_load_28_range_W'][0]}-{hd['P_load_28_range_W'][1]} W measured at 28 V in; "
                               "harness/filters excluded; strong part-load dependence; no accessed 28 V-class point above "
                               "about 1 kW",
              "note": "range = min/max over the measured 28 V-input points of both output-voltage series; the "
                      "all-input-voltage range spans 25/28/34 V in (bus voltage is an owner decision)"}
    hd_load = _tbd("an admitted Hall transport closure (credible set empty, gate 3 FAIL) or a Vyovrinda hardware "
                   "measurement of V_d x I_d", "physics track: admission of a closure (fo_absolute_comparison); "
                   "every absolute Hall number is withdrawn")
    comps["hall_discharge"] = {
        "in_architectures": list(ARCHS),
        "modes": {
            "steady": {"load": hd_load, "efficiency": hd_eff,
                       "bus_draw": {"status": "TBD", "reason": "load TBD", **_per_unit(*hd["eta28"])},
                       "loss": {"status": "TBD", "reason": "load TBD"}},
            "startup": {"load": _tbd("discharge-ignition load of an admitted closure or hardware measurement",
                                     "physics track (gate 3)"),
                        "efficiency": copy.deepcopy(hd_eff),
                        "bus_draw": {"status": "TBD", "reason": "load TBD", **_per_unit(*hd["eta28"])},
                        "loss": {"status": "TBD", "reason": "load TBD"}},
        },
        "measured_supply_points_28V": hd["points28"],
    }

    # ---- hall_magnet
    pm = E("hall_magnet", "HM-PM-OPTION")
    hm_model = E("hall_magnet", "HM-MODEL")
    hm_eff = E("hall_magnet", "HM-SUPPLY-EFF")
    rf100 = mp.resistance_factor(mp.ANNEALED_COPPER_IACS, 100.0)
    rf200 = mp.resistance_factor(mp.ANNEALED_COPPER_IACS, 200.0)
    hm_mode = {
        "load": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "P_load_W": pm["value"], "evidence_class": "definition",
             "entry_ids": [pm["id"]], "condition": "owner selects a permanent-magnet Hall circuit (lane 20 open question 3)"},
            {"option": "electromagnet", **_tbd("the Vyovrinda magnetic-circuit geometry, field and coil temperature fed "
                                               "into abep_sim.magnet_power.electromagnet", "Vyovrinda thruster design "
                                               "(not a Hall-closure quantity)", [hm_model["id"]])}],
                 "relation": "P_load = (N I)^2 rho(T) l_mt / (k A_w), so P_load is proportional to B_gap^2 at fixed "
                             "geometry and to [1 + 0.00393 (T - 20 C)] (magnet_power E3/E5)",
                 "evidence_class": "model-derived"},
        "efficiency": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "value": 1.0, "evidence_class": "definition", "entry_ids": [pm["id"]]},
            {"option": "electromagnet", **_tbd(hm_eff["tbd_requires"], "measured magnet-supply efficiency "
                                               "(supply-efficiency campaign)", [hm_eff["id"]])}]},
        "bus_draw": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "P_bus_W": 0.0, "status": "ZERO_CONDITIONAL",
             "condition": "permanent-magnet Hall circuit (0 W, efficiency 1, passed explicitly)"},
            {"option": "electromagnet", "status": "TBD", "reason": "load and supply efficiency TBD",
             "bound": "P_bus >= P_load (efficiency <= 1 by definition)"}]},
        "loss": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "P_loss_W": 0.0, "status": "ZERO_CONDITIONAL"},
            {"option": "electromagnet", "status": "TBD"}]},
    }
    comps["hall_magnet"] = {"in_architectures": list(ARCHS), "modes": {"steady": hm_mode, "startup": copy.deepcopy(hm_mode)},
                            "coil_resistance_factor_vs_20C": {"100C": _sig(rf100, 5), "200C": _sig(rf200, 5),
                                                              "source": "abep_sim.magnet_power.resistance_factor "
                                                                        "(NBS Handbook 100, alpha_20 = 0.00393 /K)",
                                                              "evidence_class": "model-derived"}}

    # ---- cathode_keeper
    ck_off = E("cathode_keeper", "CK-G&K-OFF")
    ck_hc3 = E("cathode_keeper", "CK-PEDRINI17-HC3")
    ck_hc1 = E("cathode_keeper", "CK-PEDRINI17-HC1")
    ck_eff = E("cathode_keeper", "CK-SUPPLY-EFF")
    kI = inp.param("jpl_ignition_keeper_current_A")
    kV = inp.param("jpl_keeper_voltage_after_ignition_V")
    k_ign = [kI["value"] * kV["value"][0], kI["value"] * kV["value"][1]]
    ck_eff_tbd = _tbd(ck_eff["tbd_requires"], "measured keeper-supply efficiency (supply-efficiency campaign)",
                      [ck_eff["id"]])
    bracket_lo = min(ck_hc1["value"]["min"], ck_hc3["value"]["min"])
    bracket_hi = max(ck_hc1["value"]["max"], ck_hc3["value"]["max"])
    comps["cathode_keeper"] = {"in_architectures": list(ARCHS), "modes": {
        "steady": {
            "load": {"status": "OPTIONS", "options": [
                {"option": "keeper_off", "P_load_W": 0.0, "evidence_class": "qualitative", "entry_ids": [ck_off["id"]],
                 "condition": "the cathode self-heats at the architecture's discharge current (keeper off after ignition, "
                              "Goebel & Katz p. 337); lane 19 Sec. 4: if I_d falls below the selected cathode's "
                              "self-heating current the keeper stays on"},
                {"option": "keeper_on", "status": "BRACKET", "range_W": [bracket_lo, bracket_hi],
                 "evidence_class": "measured", "evidence_level": [3, 6], "entry_ids": [ck_hc1["id"], ck_hc3["id"]],
                 "note": "keeper-only discharges (keeper as the only anode) of SITAEL HC1/HC3: a bracket from other "
                         "hardware, not a Vyovrinda keeper load; lane 20 reads HC3 as the upper bracket"}]},
            "efficiency": {"status": "OPTIONS", "options": [
                {"option": "keeper_off", "value": 1.0, "evidence_class": "definition",
                 "note": "0 W passed explicitly; any efficiency gives 0 W bus draw, 1.0 follows the boundary's "
                         "zero-power convention"},
                {"option": "keeper_on", **ck_eff_tbd}]},
            "bus_draw": {"status": "OPTIONS", "options": [
                {"option": "keeper_off", "P_bus_W": 0.0, "status": "ZERO_CONDITIONAL"},
                {"option": "keeper_on", "status": "TBD", "reason": "supply efficiency TBD",
                 "bound": "P_bus >= P_load (efficiency <= 1)"}]},
            "loss": {"status": "OPTIONS", "options": [{"option": "keeper_off", "P_loss_W": 0.0, "status": "ZERO_CONDITIONAL"},
                                                      {"option": "keeper_on", "status": "TBD"}]},
        },
        "startup": {
            "load": {"status": "BRACKET", "range_W": [_sig(k_ign[0]), _sig(k_ign[1])], "evidence_class": "inferred",
                     "derivation": f"keeper current regulated to {kI['value']} A x keeper voltage "
                                   f"{kV['value'][0]}-{kV['value'][1]} V after ignition (product of two reported "
                                   "quantities of the JPL 1.5-cm LaB6 procedure)",
                     "entry_ids": ["jpl_ignition_keeper_current_A", "jpl_keeper_voltage_after_ignition_V"],
                     "evidence": [_ref_cd("jpl_ignition_keeper_current_A", kI, "measured"),
                                  _ref_cd("jpl_keeper_voltage_after_ignition_V", kV, "measured")],
                     "note": "the 150 V ignition voltage is applied before the current flows; a different cathode "
                             "class, not a Vyovrinda value"},
            "efficiency": ck_eff_tbd,
            "bus_draw": {"status": "LOWER_BOUND", "P_bus_W_at_least": [_sig(k_ign[0]), _sig(k_ign[1])],
                         "derivation": "P_bus >= P_load because efficiency <= 1 (definition); bracket, design-dependent"},
            "loss": {"status": "TBD", "reason": "supply efficiency TBD"},
        }}}

    # ---- cathode_heater
    ch_off = E("cathode_heater", "CH-G&K-STEADY-OFF")
    ch_hc1 = E("cathode_heater", "CH-PEDRINI17-HC1")
    ch_hc3 = E("cathode_heater", "CH-PEDRINI17-HC3")
    ch_mon = E("cathode_heater", "CH-MONTERO24")
    ch_eff = E("cathode_heater", "CH-SUPPLY-EFF")
    h6 = inp.param("jpl_h6_lab6_heater_W")
    heater_vals = [ch_hc1["value"], ch_hc3["value"], h6["value"], ch_mon["value"]["min"], ch_mon["value"]["max"]]
    h_lo, h_hi = min(heater_vals), max(heater_vals)
    energy = inp.cdd["startup_heater_energy"]
    comps["cathode_heater"] = {"in_architectures": list(ARCHS), "modes": {
        "steady": {
            "load": {"status": "ZERO_CONDITIONAL", "P_load_W": 0.0, "evidence_class": "qualitative",
                     "entry_ids": [ch_off["id"]], "condition": "cathode self-heating once the discharge is on "
                     "(heater off; Goebel & Katz p. 337); lane 19 steady policy"},
            "efficiency": {"status": "DEFINITION", "value": 1.0, "evidence_class": "definition",
                           "note": "boundary convention: heater off in the mode = 0 W with efficiency 1, explicit"},
            "bus_draw": {"status": "ZERO_CONDITIONAL", "P_bus_W": 0.0},
            "loss": {"status": "ZERO_CONDITIONAL", "P_loss_W": 0.0}},
        "startup": {
            "load": {"status": "BRACKET", "range_W": [h_lo, h_hi], "evidence_class": "measured",
                     "evidence_level": [3, 6],
                     "entry_ids": [ch_hc1["id"], ch_hc3["id"], "jpl_h6_lab6_heater_W", ch_mon["id"]],
                     "note": "ignition heater power across four LaB6 designs (SITAEL HC1 about 45 W, HC3 about 60 W, "
                             "JPL H6 cathode 120 W routine, UC3M 267-305 W): the design spread, not a Vyovrinda "
                             "value; preheat phase and cathode-ignition phase only (heater off at discharge ignition)"},
            "efficiency": _tbd(ch_eff["tbd_requires"], "measured heater-supply efficiency (supply-efficiency campaign)",
                               [ch_eff["id"]]),
            "bus_draw": {"status": "LOWER_BOUND", "P_bus_W_at_least": [h_lo, h_hi],
                         "derivation": "P_bus >= P_load because efficiency <= 1 (definition); design-dependent bracket"},
            "loss": {"status": "TBD", "reason": "supply efficiency TBD"},
            "energy_per_start_load_Wh": [{"heater_W": r["heater_W"], "time_s": r["time_s"],
                                          "energy_Wh": _sig(r["energy_Wh"]),
                                          "source": "cathode_integration_derived_v1.startup_heater_energy (SITAEL HC1)",
                                          "evidence_class": "inferred"} for r in energy],
        }}}

    # ---- flow_control
    fc = E("flow_control", "FC-MOOG-I2R")
    fc_air = E("flow_control", "FC-AIR-VALVE")
    fc_eff = E("flow_control", "FC-DRIVER-EFF")
    fc_mode = {
        "load": {"status": "PARTIAL", "per_energized_xe_pfcv_W": [fc["value"]["min"], fc["value"]["max"]],
                 "evidence_class": fc["evidence_class"], "evidence_level": fc["evidence_level"], "entry_ids": [fc["id"]],
                 "missing": [_tbd("number of simultaneously energized valves per mode (design / upstream ICD)",
                                  "upstream ICD lane_33_upstream_icd (single-lens-v1, not verified)"),
                             _tbd(fc_air["tbd_requires"], "upstream ICD lane_33_upstream_icd", [fc_air["id"]])],
                 "note": "coil I^2R at 21 C of one Moog 51E339 Xe PFCV; the air-path valve and the valve count are TBD"},
        "efficiency": _tbd(fc_eff["tbd_requires"], "valve-driver design data", [fc_eff["id"]]),
        "bus_draw": {"status": "LOWER_BOUND_PER_VALVE", "P_bus_W_at_least_per_energized_xe_pfcv":
                     [fc["value"]["min"], fc["value"]["max"]],
                     "derivation": "P_bus >= P_load (efficiency <= 1); total needs the valve count and the air valve"},
        "loss": {"status": "TBD", "reason": "driver efficiency TBD"},
    }
    comps["flow_control"] = {"in_architectures": list(ARCHS), "modes": {"steady": fc_mode, "startup": copy.deepcopy(fc_mode)}}

    # ---- compressor
    cp_load = E("compressor", "CP-LOAD")
    cp_eff = E("compressor", "CP-CONV-EFF")
    cp_mode = {
        "load": _tbd(cp_load["tbd_requires"] + "; the valve-outlet feed state (lane_16) is never filled here",
                     "upstream ICD lane_33_upstream_icd not verified (single-lens-v1); abep_sim.compressor inputs "
                     "eta_motor / P_ctrl / k_bear unsourced", [cp_load["id"], "CP-REPO-MODEL"]),
        "efficiency": _tbd(cp_eff["tbd_requires"], "motor-drive converter data", [cp_eff["id"]]),
        "bus_draw": {"status": "TBD", "reason": "load and efficiency TBD (never filled in this lane)"},
        "loss": {"status": "TBD", "reason": "load and efficiency TBD"},
    }
    comps["compressor"] = {"in_architectures": list(ARCHS),
                           "modes": {"steady": cp_mode, "startup": {**copy.deepcopy(cp_mode), "phase_note":
                                     "lane 19 start-up order powers the compressor only in the keeper-off phase"}}}

    # ---- thermal_control
    tc_load, tc_eff = E("thermal_control", "TC-LOAD"), E("thermal_control", "TC-EFF")
    tc_mode = {"load": _tbd(tc_load["tbd_requires"], "lane_15_thermal_life evaluated with sourced inputs",
                            [tc_load["id"]]),
               "efficiency": _tbd(tc_eff["tbd_requires"], "heater-switch topology data", [tc_eff["id"]]),
               "bus_draw": {"status": "TBD", "reason": "load and efficiency TBD"}, "loss": {"status": "TBD", "reason": "load and efficiency TBD"}}
    comps["thermal_control"] = {"in_architectures": list(ARCHS), "modes": {"steady": tc_mode, "startup": copy.deepcopy(tc_mode)}}

    # ---- housekeeping
    hk_load, hk_eff = E("housekeeping", "HK-LOAD"), E("housekeeping", "HK-EFF")
    hk_mode = {"load": _tbd(hk_load["tbd_requires"] + "; never 0 W (BUS_POWER_BOUNDARY Sec. 3); for rf_hall/ecr_hall it "
                            "also carries the pre-ionizer controller and any pre-ionizer standby draw (v1 limitation, "
                            "BUS_POWER_BOUNDARY Sec. 2)", "controller / telemetry electronics selection", [hk_load["id"]]),
               "efficiency": _tbd(hk_eff["tbd_requires"], "converter data", [hk_eff["id"]]),
               "bus_draw": {"status": "TBD", "reason": "load and efficiency TBD"}, "loss": {"status": "TBD", "reason": "load and efficiency TBD"}}
    comps["housekeeping"] = {"in_architectures": list(ARCHS), "modes": {"steady": hk_mode, "startup": copy.deepcopy(hk_mode)}}

    # ---- pre-ionizer source components
    floor = inp.ecr["ionization_floor"]
    floors = {k: {"W_per_A": v["value_W_per_A"], "feed": v["feed"], "evidence_class": "model-derived",
                  "source": "overlay_ecr_v1.ionization_floor (interstage_v1 catalogue, NIST ionization energies)"}
              for k, v in sorted(floor["values"].items())}
    floor_rule = {"floors": floors, "air_mixture_feed": floor["air_mixture_feed"],
                  "relation": "P_load[source] >= eps_floor x I_src and P_bus[source] >= P_load[source] "
                              "(I_src = ion current leaving the source exit, A; eps_floor in W/A = eV per charge); "
                              "the floor holds at every power plane (energy conservation)",
                  "evidence_class": "model-derived"}

    rf_ev = inp.rf["rf_source_chain_evidence"]
    rf_lo, rf_hi = rf_ev["range"]
    rf_no = E("rf_source", "RF-NEWORBIT25")
    rf_vk = E("rf_source", "RF-VOLKMAR18")
    rf_match = E("rf_source", "RF-MATCH-LOSS")
    rf_load = E("rf_source", "RF-LOAD")
    rf_mode = {
        "load": {**_tbd(rf_load["tbd_requires"], "pre-ionizer physics / RF source measurement on air/N2 at the ICD "
                        "inlet state (lane 06 experiment protocol)", [rf_load["id"]]), "lower_bound": floor_rule},
        "efficiency": {"status": "EVIDENCE_RANGE", "range": [rf_lo, rf_hi], "entry_ids": [rf_no["id"], rf_vk["id"]],
                       "evidence": [_ref_ec(rf_no), _ref_ec(rf_vk)], "evidence_class": "measured/inferred",
                       "note": rf_ev["note"], "missing": [_tbd(rf_match["tbd_requires"], "RF chain measurement",
                                                               [rf_match["id"]])]},
        "bus_draw": {"status": "TBD", "reason": "load TBD", **_per_unit(rf_lo, rf_hi),
                     "lower_bound": "P_bus[rf_source] >= eps_floor x I_src (floor above)"},
        "loss": {"status": "TBD", "reason": "load TBD"},
    }
    comps["rf_source"] = {"in_architectures": ["rf_hall"], "modes": {
        "steady": rf_mode,
        "startup": {**copy.deepcopy(rf_mode), "phase_note": "PROPOSED variants (lane 19): V1 pre-ionizer on after "
                    "keeper-off (never overlaps the heater); V2 on during cathode/discharge ignition"}}}

    ec_ev = inp.ecr["bus_chain_evidence"]
    ref_chain = ec_ev["reference_chain"]["value"]
    stage = [(s["id"], s["value"]) for s in ec_ev["stage_only_upper_bounds"]]
    stage_vals = []
    for sid, v in stage:
        if isinstance(v, dict):
            for k in ("drain_efficiency", "PAE"):
                stage_vals.append((f"{sid}:{k}", v[k]))
        else:
            stage_vals.append((sid, v))
    ec_iso = E("ecr_source", "EC-ISOLATOR-FEED")
    ec_load = E("ecr_source", "EC-LOAD")
    ecr_mode = {
        "load": {**_tbd(ec_load["tbd_requires"], "pre-ionizer physics / ECR source measurement on air/N2 at the ICD "
                        "inlet state (lane 06 experiment protocol)", [ec_load["id"]]), "lower_bound": floor_rule},
        "efficiency": {"status": "REFERENCE_AND_STAGE_BOUNDS", "reference_chain": ref_chain,
                       "reference_chain_evidence": {"id": "EC-HAYABUSA-TWTA", "evidence_class": "inferred",
                                                    "evidence_level": 3,
                                                    "applicability": "4.2 GHz TWT system, 40 W RF / 110 W DC, flight"},
                       "stage_only_upper_bounds": [{"id": i, "value": v} for i, v in stage_vals],
                       "note": "stage-only values bound the chain that contains that stage from above; only the "
                               "Hayabusa value is system-level; the ABEP chain may be higher or lower than it",
                       "missing": [_tbd(ec_iso["tbd_requires"], "isolator/feed measurement", [ec_iso["id"]])]},
        "bus_draw": {"status": "TBD", "reason": "load TBD",
                     "bus_W_per_W_load_reference_chain": _sig(1.0 / ref_chain),
                     "bus_W_per_W_load_at_least_for_stage_technology": {i: _sig(1.0 / v) for i, v in stage_vals},
                     "lower_bound": "P_bus[ecr_source] >= eps_floor x I_src (floor above)"},
        "loss": {"status": "TBD", "reason": "load TBD"},
    }
    comps["ecr_source"] = {"in_architectures": ["ecr_hall"], "modes": {
        "steady": ecr_mode,
        "startup": {**copy.deepcopy(ecr_mode), "phase_note": "PROPOSED variants (lane 19): V1 ecr_magnet then "
                    "ecr_source after keeper-off; V2 both before discharge ignition"}}}

    em_pm = E("ecr_magnet", "EM-PM-OPTION")
    em_b = E("ecr_magnet", "EM-RESONANCE-B")
    em_eff = E("ecr_magnet", "EM-SUPPLY-EFF")
    fo = inp.ecr["fixed_overhead"]["electromagnet_option"]
    em_mode = {
        "load": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "P_load_W": em_pm["value"], "evidence_class": "definition",
             "entry_ids": [em_pm["id"]], "condition": "owner selects a permanent-magnet ECR circuit"},
            {"option": "electromagnet", **_tbd("the ECR coil geometry at the resonance field fed into "
                                               "abep_sim.magnet_power.electromagnet", "Vyovrinda ECR stage design",
                                               ["EM-MODEL"]),
             "field_required_T": em_b["value"], "field_evidence_class": em_b["evidence_class"],
             "relation": "at identical circuit geometry the coil power scales as (B_ECR / B_Hall)^2 (magnet_power E5)",
             "open_evidence": fo["reading"]}]},
        "efficiency": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "value": 1.0, "evidence_class": "definition"},
            {"option": "electromagnet", **_tbd(em_eff["tbd_requires"], "measured magnet-supply efficiency", [em_eff["id"]])}]},
        "bus_draw": {"status": "OPTIONS", "options": [
            {"option": "permanent_magnet", "P_bus_W": 0.0, "status": "ZERO_CONDITIONAL"},
            {"option": "electromagnet", "status": "TBD", "bound": "P_bus >= P_load (efficiency <= 1)"}]},
        "loss": {"status": "OPTIONS", "options": [{"option": "permanent_magnet", "P_loss_W": 0.0, "status": "ZERO_CONDITIONAL"},
                                                  {"option": "electromagnet", "status": "TBD"}]},
    }
    comps["ecr_magnet"] = {"in_architectures": ["ecr_hall"], "modes": {"steady": em_mode, "startup": copy.deepcopy(em_mode)}}
    return comps, hd


# ------------------------------------------------------------------------------------------------ ledgers
def _fully_sourced(comp: dict, mode: str):
    """(loads, effs) for one component if the steady/startup entry has one sourced number each, else None."""
    m = comp["modes"][mode]
    ld, ef = m["load"], m["efficiency"]
    if ld.get("status") in ("ZERO_CONDITIONAL",) and ef.get("status") == "DEFINITION":
        return ld["P_load_W"], ef["value"], "conditional"
    return None


def try_ledgers(comps: dict, ab) -> list:
    """Every (architecture, mode) ledger through bus_power_ledger itself, with only sourced inputs.

    Only the components whose load AND efficiency are sourced single values are passed. The boundary refuses any
    incomplete set (it defaults nothing); its own refusal message is recorded verbatim. A ledger is EVALUATED only if
    the boundary accepts it.
    """
    out = []
    for arch in ARCHS:
        req = list(ab.REQUIRED_COMPONENTS[arch])
        for mode in MODES:
            loads, effs, blocking, conditional = {}, {}, [], []
            for c in req:
                got = _fully_sourced(comps[c], mode)
                if got is None:
                    blocking.append(c)
                    continue
                loads[c], effs[c], tag = got
                if tag == "conditional":
                    conditional.append(c)
            try:
                led = ab.bus_power_ledger(arch, loads, effs)
                out.append({"architecture": arch, "mode": mode, "status": "EVALUATED", "ledger": led,
                            "conditional_components": conditional})
            except ValueError as exc:
                out.append({"architecture": arch, "mode": mode, "status": "NOT_EVALUABLE",
                            "boundary_refusal": str(exc), "sourced_components_passed": sorted(loads),
                            "conditional_components": conditional, "blocking_components": blocking})
    return out


# ------------------------------------------------------------------------------------------------ differential
DIFF_CLASSES = ("NOT_COMMON", "COMMON_MODE", "COMMON_MODE_CONDITIONAL", "ARCH_SPECIFIC")


def differential(comps: dict, hd: dict, ab) -> dict:
    common = list(ab.COMMON_COMPONENTS)
    rows = {
        "hall_discharge": ("NOT_COMMON",
                           "DeltaP_bus,d = P_d,arm / eta_d(P_d,arm) - P_d,ho / eta_d(P_d,ho)",
                           "the pre-ionizer changes the discharge load at the common feed state (Hall block, gate 3); the "
                           "discharge-supply efficiency is part-load dependent (lane 20 HD-RH24 series), so even the "
                           "conversion loss differs when P_d differs. This is the only term through which a pre-ionizer "
                           "can save bus power (breakeven_v1 Sec. 4)", "TBD (gate 3)"),
        "hall_magnet": ("COMMON_MODE_CONDITIONAL",
                        "DeltaP_bus,mag = P_mag,ho (r(T_arm)/r(T_ho) - 1) / eta_mag at equal field",
                        "same downstream Hall accelerator and field: cancels exactly at equal coil temperature (or 0 W "
                        "for a permanent magnet in both); a different coil temperature changes the I^2R by the copper "
                        "resistance factor r(T) = 1 + 0.00393 (T - 20 C) (magnet_power E3)", "0 W if common temperature or PM"),
        "cathode_keeper": ("COMMON_MODE_CONDITIONAL", "DeltaP_bus,k = I_k V_k / eta_k when the policies differ",
                           "same cathode and policy: cancels; breaks when an architecture's discharge current falls below "
                           "the selected cathode's self-heating current so its keeper must stay on (lane 19 Sec. 4); at a "
                           "fixed bus limit the pre-ionized arms reach this first", "0 W if the same policy holds"),
        "cathode_heater": ("COMMON_MODE", "0 (steady: off in all; start-up: identical cathode and heater)",
                           "lane 19 Sec. 7: the cathode loads themselves are identical across architectures; only the "
                           "start-up PEAK differs, through pre-ionizer overlap (variant V2), which is booked on the "
                           "source components", "0 W"),
        "flow_control": ("COMMON_MODE_CONDITIONAL", "0 if the pre-ionizer adds no feed actuator",
                         "common feed state (breakeven_v1 A7): same valves, same flows; a pre-ionizer that needs its own "
                         "feed actuator would add its coil power here (design question)", "0 W unless a source valve is added"),
        "compressor": ("COMMON_MODE", "0",
                       "the flow is fixed by the common feed state; pre-ionizer and Hall-closure uncertainty never leak "
                       "upstream into the intake/compressor/gas chambers/valves (CLAUDE.md scope)", "0 W"),
        "thermal_control": ("COMMON_MODE_CONDITIONAL", "DeltaP_bus,tc from any heater the pre-ionizer hardware needs",
                            "common gas-path and Xe heaters cancel; a pre-ionizer may add heaters or change the thermal "
                            "balance of the PPU/gas chamber (lane_15 thermal/life)", "TBD (lane 15)"),
        "housekeeping": ("NOT_COMMON", "DeltaP_bus,hk = pre-ionizer control electronics + standby / eta_hk",
                         "bus_power_boundary_v1 books pre-ionizer controller and standby (idle) draw under housekeeping "
                         "(BUS_POWER_BOUNDARY Sec. 2 v1 limitation), so it does not cancel", "TBD (> 0 for an active pre-ionizer controller)"),
    }
    base = {}
    for c in common:
        cls, formula, reason, value = rows[c]
        base[c] = {"class": cls, "formula": formula, "reason": reason, "value": value}
    arms = {}
    for arch in ("rf_hall", "ecr_hall"):
        extra = list(ab.PREIONIZER_COMPONENTS[arch])
        terms = copy.deepcopy(base)
        for c in extra:
            if c == "ecr_magnet":
                terms[c] = {"class": "ARCH_SPECIFIC", "formula": "P_bus[ecr_magnet] = P_load/eta (0 W for a permanent magnet)",
                            "reason": "no hall_only counterpart; the ECR resonance field is separate from the Hall field "
                                      "in bus_power_boundary_v1", "value": "0 W (PM) or TBD (electromagnet)"}
            else:
                terms[c] = {"class": "ARCH_SPECIFIC", "formula": f"P_bus[{c}] = P_load[{c}] / eta_chain >= eps_floor I_src",
                            "reason": "no hall_only counterpart", "value": "TBD (load); per-unit bus multiplier in the component table"}
        cancel = sorted(c for c, t in terms.items() if t["class"] == "COMMON_MODE")
        cond = sorted(c for c, t in terms.items() if t["class"] == "COMMON_MODE_CONDITIONAL")
        noncommon = sorted(c for c, t in terms.items() if t["class"] in ("NOT_COMMON", "ARCH_SPECIFIC"))
        src = " + ".join(f"P_bus[{c}]" for c in extra)
        arms[f"{arch}-hall_only"] = {
            "terms": terms,
            "cancels": cancel, "cancels_conditionally": cond, "does_not_cancel": noncommon,
            "total": f"DeltaP_bus({arch} - hall_only) = DeltaP_bus,d + {src} + DeltaP_bus,hk + "
                     "sum over the conditional common terms",
            "overhead_for_breakeven": f"O = {src} + sum over common components except hall_discharge of "
                                      "(P_bus,arm - P_bus,hall_only); omega = O / P_d,bus0 (BREAKEVEN_DERIVATION Sec. 4, "
                                      "v1-conformant: P_interstage = P_extraPPU = 0)",
            "sourced_lower_bound": f"DeltaP_bus - DeltaP_bus,d >= {src} >= eps_floor x I_src when every conditional "
                                   "common term is 0 and housekeeping does not decrease (eps_floor: N2 feed 14.5341 W/A, "
                                   "Xe feed 12.1298 W/A; air mixture TBD)",
            "numeric_value": "TBD: no pre-ionizer load, no housekeeping delta and no Hall discharge delta is sourced",
        }
    return {"classes": list(DIFF_CLASSES), "arms": arms}


# ------------------------------------------------------------------------------------------------ headroom
def headroom(inp: Inputs, hd: dict) -> dict:
    g2 = [g for g in inp.hgm["gates"] if g["id"] == "G2_bus_power"]
    if not g2:
        raise AuxBusInputError("hard_gate_matrix has no G2_bus_power gate")
    crit = [c for c in g2[0]["criteria"] if c["id"] == "G2.bus_power_max"][0]
    limit = crit["threshold"]
    lo, hi = hd["eta28"]
    return {
        "limit_W": limit, "limit_status": crit["threshold_status"], "limit_source": crit["threshold_source"],
        "scope_open": ["whether the RFP '< 1.5 kW' refers to bus_power_boundary_v1 (BUS_POWER_BOUNDARY Sec. 5 rule 6; "
                       "owner)", "every mode vs steady only (hard-gate reading OD8)",
                       "floor with or without Xe augmentation (hard-gate reading OD4)"],
        "definitions": {"A_arch": "sum over every bus_power_boundary_v1 component of arch except hall_discharge of "
                                  "P_load / eta (auxiliary + pre-ionizer bus draw, same mode)",
                        "P_d": "Hall discharge load-plane power V_d I_d (unknown: no admitted closure)",
                        "eta_d(P_d)": "discharge-supply efficiency at P_d (part-load dependent)"},
        "inequalities": {
            "general": f"P_d / eta_d(P_d) + A_arch < {limit} W",
            "discharge_allowance": f"P_d < eta_d(P_d) x ({limit} W - A_arch)",
            "necessary_any_supply": f"P_d < {limit} W - A_arch  (eta_d <= 1 by definition)",
            "auxiliary_allowance": f"A_arch < {limit} W - P_d / eta_d(P_d)",
            "hall_only": f"A_ho = P_bus[hall_magnet] + P_bus[cathode_keeper] + P_bus[cathode_heater] + P_bus[flow_control] "
                         f"+ P_bus[compressor] + P_bus[thermal_control] + P_bus[housekeeping]",
            "rf_hall": "A_rf = A_ho(rf loads) + P_bus[rf_source],  P_bus[rf_source] >= eps_floor I_src",
            "ecr_hall": "A_ecr = A_ho(ecr loads) + P_bus[ecr_source] + P_bus[ecr_magnet],  P_bus[ecr_source] >= eps_floor I_src",
            "payable_source_current": f"I_src < ({limit} W - P_d,arm / eta_d(P_d,arm) - A_common,arm) / eps_floor "
                                      "(necessary; eps_floor N2 14.5341 W/A, Xe 12.1298 W/A)",
        },
        "eta_d_measured_range_28V": [lo, hi],
        "discharge_allowance_coefficient": f"eta_d in [{lo}, {hi}] at the measured 28 V-input points only",
        "measured_point_table_note": "aux_allowance_below_1500W_W in components.hall_discharge.measured_supply_points_28V "
                                     "= 1500 W - P_d/eta_d at the breadboard supply's own test points: IF the discharge "
                                     "load equals that test point and the supply performs as measured, THEN A_arch must "
                                     "stay below it. Test points are not Vyovrinda discharge powers.",
        "numeric_headroom": "TBD: P_d is withdrawn (gate 3) and A_arch has no sourced value in any mode",
    }


# ------------------------------------------------------------------------------------------------ start-up
def startup(inp: Inputs, comps: dict, ab) -> dict:
    ref = inp.cd["startup_reference"]
    phases = ref["hall_only"]["phases"]
    for ph in phases:
        bad = set(ph["on"]) - set(ab.COMMON_COMPONENTS)
        if bad:
            raise AuxBusInputError(f"start-up phase {ph['name']} names components outside the boundary: {sorted(bad)}")
    h = comps["cathode_heater"]["modes"]["startup"]["load"]["range_W"]
    k = comps["cathode_keeper"]["modes"]["startup"]["load"]["range_W"]
    lb = {"preheat": {"P_bus_W_at_least": [h[0], h[1]], "from": "cathode_heater (bracket) + housekeeping (TBD, >= 0)"},
          "cathode_ignition": {"P_bus_W_at_least": [_sig(h[0] + k[0]), _sig(h[1] + k[1])],
                               "from": "cathode_heater + cathode_keeper brackets (+ flow_control, housekeeping >= 0); "
                                       "the brackets come from different cathodes, so the sum is a bracket, not a design"},
          "discharge_ignition": {"P_bus_W_at_least": "TBD", "from": "hall_discharge ignition load TBD (gate 3)"},
          "keeper_off": {"P_bus_W_at_least": "TBD", "from": "steady-mode ledger (hall_discharge TBD)"}}
    return {
        "phase_order": [{"phase": ph["name"], "on": ph["on"], "note": ph["note"]} for ph in phases],
        "phase_order_status": ref["hall_only"]["status"],
        "variants": {a: {"status": ref[a]["status"], **ref[a]["variants"]} for a in ("rf_hall", "ecr_hall")},
        "phase_bus_lower_bounds_all_architectures": lb,
        "differential": {
            "V1_preionizer_after_discharge": "start-up phases identical across the three architectures up to keeper-off; "
                                             "the pre-ionizer adds P_bus[source] (+ P_bus[ecr_magnet]) only in the "
                                             "steady (keeper-off) mode, so the start-up differential before steady is 0 W",
            "V2_preionizer_seed_before_discharge": "during cathode/discharge ignition the pre-ionized arms add "
                                                   "P_bus[source] (+ P_bus[ecr_magnet]) on top of the phase load; with the "
                                                   "heater still on the start-up peak of rf_hall/ecr_hall exceeds the "
                                                   "hall_only level by that source bus draw (lane 19 Sec. 7)",
        },
        "peak_limit": {"value_W": inp.cd["proposed_thresholds"]["startup_peak_limit"]["value"],
                       "status": inp.cd["proposed_thresholds"]["startup_peak_limit"]["status"],
                       "note": inp.cd["proposed_thresholds"]["startup_peak_limit"]["note"]},
        "startup_ledger": "NOT_EVALUABLE (see ledgers): hall_discharge ignition load, supply efficiencies, housekeeping "
                          "TBD; abep_sim.cathode_integration.startup_transient is the function to use once they exist",
    }


# ------------------------------------------------------------------------------------------------ hard gates
def hard_gate_check(hg) -> dict:
    res = hg.evaluate_all([])
    return {
        "evaluator": "abep_sim.hard_gates.evaluate_all(evidence=[]) (lane_24_hard_gates)",
        "evidence_submitted": [],
        "why_no_evidence": "G2.bus_power_max FAILs only on a lower bound >= 1500 W of architecture scope in steady mode "
                           "on both feeds. Every auxiliary lower bound this lane can derive is design-dependent (cathode "
                           "brackets, per-valve coil power) or proportional to an unknown source current (eps_floor "
                           "I_src), and the hall_discharge load is withdrawn; none is a verdict-bearing bound, and a PASS "
                           "needs the complete ledger, which is not evaluable.",
        "G2_bus_power_verdicts": {a: res["architectures"][a]["gates"]["G2_bus_power"]["verdict"] for a in ARCHS},
        "eliminated": res["eliminated"], "not_eliminated": res["not_eliminated"],
        "matrix_version": res["matrix_version"], "matrix_status": res["matrix_status"],
        "admitted_members": res["admitted_members"],
    }


# ------------------------------------------------------------------------------------------------ cross-checks
def self_checks(inp: Inputs, comps: dict, hd: dict) -> dict:
    we = inp.we
    rows = {(r["V_out_V"], r["P_load_W"]): r for r in we["discharge_28Vin_measured_points"]["rows"]}
    dev = 0.0
    for r in hd["points28"]:
        w = rows.get((r["V_out_V"], r["P_load_W"]))
        if w is None:
            raise AuxBusInputError(f"worked example lacks the 28 V point {r['V_out_V']} V / {r['P_load_W']} W")
        dev = max(dev, abs(w["P_bus_W"] - r["P_bus_W"]))
    spread = we["efficiency_spreads"]["ecr_source"]["bus_W_per_100W_delivered"]["hayabusa_twta_system"]
    mine = 100.0 * comps["ecr_source"]["modes"]["steady"]["bus_draw"]["bus_W_per_W_load_reference_chain"]
    ok1 = dev <= 1e-3
    ok2 = abs(spread - mine) <= 0.01
    if not (ok1 and ok2):
        raise AuxBusInputError(f"cross-check against lane 20 worked example failed (discharge {dev}, ecr {spread} vs {mine})")
    return {"discharge_points_vs_lane20_worked_example": {"n": len(hd["points28"]), "max_abs_dev_W": _sig(dev), "pass": ok1},
            "ecr_reference_chain_vs_lane20_worked_example": {"lane20_bus_W_per_100W": spread, "this": _sig(mine), "pass": ok2}}


# ------------------------------------------------------------------------------------------------ assembly
TBD_REGISTER = [
    ("hall_discharge", "load", "admitted Hall transport closure or hardware V_d I_d", "physics track (gate 3; credible set empty)"),
    ("hall_discharge", "efficiency above ~1 kW / at the chosen bus voltage", "measured discharge-supply efficiency at the "
     "Vyovrinda bus voltage and load; Rhodes 2024 full paper for definition and uncertainty", "owner bus-voltage decision; supply test"),
    ("hall_magnet", "load", "Vyovrinda magnetic circuit into magnet_power.electromagnet, or PM decision", "thruster design; owner"),
    ("hall_magnet", "efficiency", "measured magnet-supply efficiency (HM-SUPPLY-EFF)", "supply-efficiency campaign"),
    ("cathode_keeper", "steady policy and load", "self-heating current of the selected cathode (dossier G01) vs each "
     "architecture's I_d", "lane 19 / cathode selection; I_d needs gate 3"),
    ("cathode_keeper", "efficiency", "measured keeper-supply efficiency (CK-SUPPLY-EFF)", "supply-efficiency campaign"),
    ("cathode_heater", "start-up load", "measured heater profile of the selected cathode", "cathode selection (milestone C)"),
    ("cathode_heater", "efficiency", "measured heater-supply efficiency (CH-SUPPLY-EFF)", "supply-efficiency campaign"),
    ("flow_control", "load", "energized valve count per mode and the air-path valve (FC-AIR-VALVE)", "lane_33_upstream_icd (not verified)"),
    ("flow_control", "efficiency", "valve-driver data (FC-DRIVER-EFF)", "driver design"),
    ("compressor", "load and efficiency", "sized compressor from the upstream ICD flow with sourced motor/drive efficiency "
     "(CP-LOAD, CP-CONV-EFF); never filled here", "lane_33_upstream_icd (not verified)"),
    ("thermal_control", "load and efficiency", "thermal model heater duty (TC-LOAD, TC-EFF)", "lane_15_thermal_life"),
    ("housekeeping", "load and efficiency", "controller/telemetry selection incl. pre-ionizer control and standby "
     "(HK-LOAD, HK-EFF)", "electronics design; owner question on v1.1 standby terms"),
    ("rf_source", "load", "net RF power at the coil feed at the operating point = source ion cost x I_src (RF-LOAD)",
     "RF source measurement on air/N2 (lane 06 protocol); pre-ionizer physics"),
    ("rf_source", "efficiency", "matchbox/cable loss at the pre-ionizer coil (RF-MATCH-LOSS)", "RF chain measurement"),
    ("ecr_source", "load", "net microwave power at the coupling input at the operating point (EC-LOAD)",
     "ECR source measurement on air/N2 (lane 06 protocol)"),
    ("ecr_source", "efficiency", "system chain incl. isolator/feed at the ECR frequency (EC-ISOLATOR-FEED)", "ECR chain measurement"),
    ("ecr_magnet", "load and efficiency", "PM vs electromagnet decision; ECR coil geometry; supply efficiency (EM-SUPPLY-EFF)",
     "ECR stage design; owner"),
    ("all", "eta_t", "interstage transport (junction capture, recombination rates, cross sections: interstage_v1 TBD list)",
     "lane_18_interstage inputs / measurement"),
]


def build(root: str = ROOT) -> dict:
    pins = verify_inputs(root)
    ab = _import("abep_sim.arch_boundary")
    if getattr(ab, "BOUNDARY_VERSION", None) != BOUNDARY_VERSION:
        raise AuxBusInputError(f"abep_sim.arch_boundary.BOUNDARY_VERSION is {getattr(ab, 'BOUNDARY_VERSION', None)!r}")
    mp = _import("abep_sim.magnet_power")
    hg = _import("abep_sim.hard_gates")
    inp = Inputs(root)
    comps, hd = build_components(inp, mp)
    for arch in ARCHS:
        missing = [c for c in ab.REQUIRED_COMPONENTS[arch] if c not in comps or arch not in comps[c]["in_architectures"]]
        if missing:
            raise AuxBusInputError(f"component table misses {missing} for {arch}")
    per_arch = {a: list(ab.REQUIRED_COMPONENTS[a]) for a in ARCHS}
    ledgers = try_ledgers(comps, ab)
    n_eval = sum(1 for l in ledgers if l["status"] == "EVALUATED")
    doc = {
        "id": VERSION,
        "follow_on": "fo_aux_bus_comparison",
        "trigger": "T_AUX_BUS",
        "prerequisites": {"lane_20_ppu_magnet": "f7c226848d", "lane_19_cathode_integration": "eff15f85c5",
                          "lane_11_bus_boundary": "a2a139686d"},
        "status": "DRAFT for owner review. Accounting of the auxiliary DC-bus power on bus_power_boundary_v1: no "
                  "absolute Hall performance, no screening candidate, no ranking, no preferred architecture; "
                  "eliminations only through abep_sim.hard_gates (none).",
        "base_commit": BASE_COMMIT,
        "boundary_version": BOUNDARY_VERSION,
        "generated_by": SCRIPT_REL,
        "regenerate": f"python {SCRIPT_REL}  (check: --check)",
        "inputs": pins,
        "architectures": list(ARCHS),
        "components_by_architecture": per_arch,
        "modes": {"steady": "keeper-off steady firing (lane 19 phase keeper_off)",
                  "startup": "preheat, cathode ignition and discharge ignition (lane 19 phase order)"},
        "evidence_classes": ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                             "definition", "qualitative", "TBD"],
        "components": comps,
        "ledgers": ledgers,
        "ledger_summary": {"attempted": len(ledgers), "evaluated": n_eval, "not_evaluable": len(ledgers) - n_eval},
        "differential": differential(comps, hd, ab),
        "startup": startup(inp, comps, ab),
        "headroom": headroom(inp, hd),
        "hard_gates": hard_gate_check(hg),
        "tbd_register": [{"component": c, "item": i, "requires": r, "blocking": b} for c, i, r, b in TBD_REGISTER],
        "milestones": {
            "supports": ["A"],
            "A": "conditional statements: 'X is baseline provided its auxiliary + pre-ionizer bus draw A_X satisfies "
                 "P_d/eta_d(P_d) + A_X < 1500 W at the admitted operating point and the conditional common-mode terms "
                 "(keeper policy, coil temperature, source feed actuator, pre-ionizer heaters) are demonstrated equal'; "
                 "the pre-ionizer bus term is bounded below by eps_floor x I_src on every chain",
            "to_reach_B": ["an admitted Hall closure (P_d per architecture)", "measured supply efficiencies (magnet, "
                           "keeper, heater, valve driver, RF/microwave chain incl. matching/isolator)", "sized compressor "
                           "from a verified upstream ICD", "thermal-control and housekeeping loads", "measured source "
                           "ion cost and eta_t on air/N2", "owner reading of the 1.5 kW scope"],
            "to_reach_C": ["a flight PPU design with every ledger evaluated in every mode", "measured start-up profile "
                           "and peak with the chosen pre-ionizer ordering", "thermal/life integration", "mission closure"],
        },
        "owner_questions": [
            "Does the RFP '< 1.5 kW' apply at bus_power_boundary_v1, and to start-up transients (lane 19 PROPOSED "
            "startup_peak_limit)?",
            "Permanent magnet or electromagnet for the Hall field and for the ECR resonance field?",
            "Steady cathode-keeper policy (off, or on below the self-heating current)?",
            "Pre-ionizer start-up ordering V1 or V2?",
            "Should v1.1 add explicit standby terms instead of booking pre-ionizer standby under housekeeping?",
        ],
        "self_checks": self_checks(inp, comps, hd),
        "not_used": ["archengine / ppu / system / plasma_devices fixed values (P_mag 25 W, controller 8 W + sensors 4 W, "
                     "aux 5 W, generator 0.65/0.90/0.80): unsourced, context only (BUS_POWER_BOUNDARY Sec. 8 R-rows)",
                     "abep_sim.arch_compare: refuses with zero admitted members (credible set empty); not needed for "
                     "an accounting without Hall maps",
                     "screening candidates sgb-screen-*: never a performance source"],
    }
    schema = _read_schema()
    hg.check_schema_keywords(schema)
    errs = hg.schema_errors(json.loads(json.dumps(doc)), schema)
    if errs:
        raise AuxBusInputError("output violates its schema:\n  " + "\n  ".join(errs[:20]))
    return doc


def _read_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def dump_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------------------------ Markdown
def _fmt_range(r) -> str:
    return f"{r[0]}–{r[1]}" if r[0] != r[1] else f"{r[0]}"


def _cell(x: dict, kind: str) -> str:
    st = x.get("status")
    if st == "TBD":
        per = ""
        if kind == "bus" and "bus_W_per_W_load" in x:
            per = f"; {_fmt_range(x['bus_W_per_W_load'])} W bus per W load"
        elif kind == "bus" and "bus_W_per_W_load_reference_chain" in x:
            per = f"; {x['bus_W_per_W_load_reference_chain']} W bus per W load at the reference chain"
        return f"TBD — {x.get('requires') or x.get('reason')}{per}"
    if st == "OPTIONS":
        parts = []
        for o in x["options"]:
            if o.get("status") == "TBD":
                parts.append(f"{o['option']}: TBD")
            elif "P_load_W" in o:
                parts.append(f"{o['option']}: {o['P_load_W']} W ({o.get('evidence_class', '')})")
            elif "value" in o:
                parts.append(f"{o['option']}: {o['value']} ({o.get('evidence_class', '')})")
            elif "P_bus_W" in o:
                parts.append(f"{o['option']}: {o['P_bus_W']} W (conditional)")
            elif "P_loss_W" in o:
                parts.append(f"{o['option']}: {o['P_loss_W']} W (conditional)")
            elif o.get("status") == "BRACKET":
                parts.append(f"{o['option']}: {_fmt_range(o['range_W'])} W bracket ({o['evidence_class']})")
            else:
                parts.append(f"{o['option']}: {o.get('status', '')}")
        return "; ".join(parts)
    if st == "BRACKET":
        return f"{_fmt_range(x['range_W'])} W bracket ({x['evidence_class']})"
    if st == "ZERO_CONDITIONAL":
        v = x.get("P_load_W", x.get("P_bus_W", x.get("P_loss_W")))
        return f"{v} W if {x.get('condition', 'the stated condition holds')}"
    if st == "DEFINITION":
        return f"{x['value']} (definition)"
    if st == "EVIDENCE_RANGE":
        return f"{_fmt_range(x['range'])} ({x['evidence_class']})"
    if st == "REFERENCE_AND_STAGE_BOUNDS":
        return (f"reference chain {x['reference_chain']} (inferred, system-level); stage-only upper bounds "
                + ", ".join(f"{s['value']}" for s in x["stage_only_upper_bounds"]))
    if st == "PARTIAL":
        return f"{_fmt_range(x['per_energized_xe_pfcv_W'])} W per energized Xe PFCV ({x['evidence_class']}); count and air valve TBD"
    if st == "LOWER_BOUND":
        return f"≥ {_fmt_range(x['P_bus_W_at_least'])} W (η ≤ 1)"
    if st == "LOWER_BOUND_PER_VALVE":
        return f"≥ {_fmt_range(x['P_bus_W_at_least_per_energized_xe_pfcv'])} W per energized PFCV"
    if kind == "bus" and "bus_W_per_W_load" in x:
        return f"TBD (load); {_fmt_range(x['bus_W_per_W_load'])} W bus per W load"
    if kind == "bus" and "bus_W_per_W_load_reference_chain" in x:
        return f"TBD (load); {x['bus_W_per_W_load_reference_chain']} W bus per W load at the reference chain"
    return st or ""


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# Auxiliary / DC-bus power comparison on `bus_power_boundary_v1` (aux_bus_comparison_v1)")
    a("")
    a("<!-- GENERATED by docs/architecture_comparison/aux_bus/build_aux_bus.py from aux_bus_comparison_v1.json; "
      "do not edit by hand -->")
    a("")
    a("| item | value |")
    a("|---|---|")
    a(f"| follow-on | `{doc['follow_on']}` (trigger `{doc['trigger']}`) |")
    a(f"| prerequisites | " + ", ".join(f"`{k}` {v}" for k, v in sorted(doc["prerequisites"].items())) + " |")
    a(f"| base commit | `{doc['base_commit']}` |")
    a(f"| data | `aux_bus_comparison_v1.json` (schema `aux_bus_comparison_v1.schema.json`) |")
    a(f"| regenerate | `{doc['regenerate']}` |")
    a(f"| status | {doc['status']} |")
    a("")
    a("## 1. Answer in short")
    a("")
    ls = doc["ledger_summary"]
    a(f"- **No full ledger is evaluable today.** {ls['attempted']} ledgers (3 architectures × steady/start-up) were "
      f"passed to `bus_power_ledger` with only their sourced inputs; the boundary refused {ls['not_evaluable']} of them "
      f"(it defaults nothing). The refusal messages are recorded in the JSON (`ledgers`).")
    a("- **What differs between the architectures.** Only `hall_discharge` (Hall block, gate 3), `housekeeping` "
      "(pre-ionizer control and standby are booked there in v1) and the pre-ionizer components (`rf_source`; "
      "`ecr_source` + `ecr_magnet`). `compressor` and `cathode_heater` cancel. `hall_magnet`, `cathode_keeper`, "
      "`flow_control` and `thermal_control` cancel only under stated conditions.")
    a("- **Sourced lower bound on the pre-ionizer term.** For every chain and power plane, "
      "P_bus[source] ≥ ε_floor · I_src with ε_floor = 14.5341 W/A on an N₂ feed and 12.1298 W/A on Xe (energy "
      "conservation on NIST ionization energies; air mixture TBD). Per watt delivered at the coupling plane the "
      "accessed chain evidence gives "
      f"{_fmt_range(doc['components']['rf_source']['modes']['steady']['bus_draw']['bus_W_per_W_load'])} W of bus for RF "
      f"and {doc['components']['ecr_source']['modes']['steady']['bus_draw']['bus_W_per_W_load_reference_chain']} W at "
      "the only system-level ECR chain (TWT, 4.2 GHz).")
    a(f"- **Headroom.** {doc['headroom']['inequalities']['general']}, i.e. "
      f"{doc['headroom']['inequalities']['discharge_allowance']}. It stays symbolic: P_d is withdrawn and A has no "
      "sourced value in any mode.")
    hgd = doc["hard_gates"]
    a(f"- **Hard gates.** `abep_sim.hard_gates.evaluate_all` with the evidence this lane can register (none is "
      f"verdict-bearing): G2 = " + ", ".join(f"{k} {v}" for k, v in hgd["G2_bus_power_verdicts"].items())
      + f"; eliminated: {hgd['eliminated'] or 'none'}. No ranking and no preferred architecture.")
    a("")
    a("## 2. Component table (per architecture × component × mode)")
    a("")
    a("Every value comes from a pinned input entry (ids in the JSON) or is TBD with what it needs. "
      "Bus draw = load / efficiency; loss = bus − load. A common component has the same row in every architecture; "
      "the pre-ionizer rows exist only in their architecture.")
    a("")
    for arch in doc["architectures"]:
        a(f"### {arch}")
        a("")
        a("| component | mode | load (load plane) | efficiency (bus → load) | bus draw | loss |")
        a("|---|---|---|---|---|---|")
        for c in doc["components_by_architecture"][arch]:
            for mode in ("steady", "startup"):
                m = doc["components"][c]["modes"][mode]
                a(f"| `{c}` | {mode} | {_cell(m['load'], 'load')} | {_cell(m['efficiency'], 'eff')} | "
                  f"{_cell(m['bus_draw'], 'bus')} | {_cell(m['loss'], 'loss')} |")
        a("")
    a("### Discharge supply at its measured 28 V-input points (Rhodes 2024 slide 11 via lane 20)")
    a("")
    a("Test points of a breadboard supply, **not** Vyovrinda discharge powers. The last column is the auxiliary + "
      "pre-ionizer allowance 1500 W − P_d/η_d IF the discharge load equalled that test point.")
    a("")
    a("| series | V_out [V] | P_load [W] | η | P_bus [W] | P_loss [W] | allowance for A [W] |")
    a("|---|---|---|---|---|---|---|")
    for r in doc["components"]["hall_discharge"]["measured_supply_points_28V"]:
        a(f"| {r['series']} | {r['V_out_V']} | {r['P_load_W']} | {r['efficiency']} | {r['P_bus_W']} | {r['P_loss_W']} | "
          f"{r['aux_allowance_below_1500W_W']} |")
    a("")
    a("## 3. Ledgers through `bus_power_ledger`")
    a("")
    a("| architecture | mode | status | sourced components passed | blocking components |")
    a("|---|---|---|---|---|")
    for l in doc["ledgers"]:
        a(f"| {l['architecture']} | {l['mode']} | {l['status']} | {', '.join(l.get('sourced_components_passed', [])) or '—'} | "
          f"{', '.join(l.get('blocking_components', [])) or '—'} |")
    a("")
    a("Components passed as sourced are only the policy-conditional zeros (heater off with efficiency 1 in steady mode). "
      "Conditional zeros for the keeper and the permanent-magnet options are listed as options, not passed, because "
      "they are owner/design choices.")
    a("")
    a("## 4. Differential terms")
    a("")
    for key, arm in doc["differential"]["arms"].items():
        a(f"### {key}")
        a("")
        a(f"`{arm['total']}`")
        a("")
        a("| component | class | term | why | value today |")
        a("|---|---|---|---|---|")
        for c, t in arm["terms"].items():
            a(f"| `{c}` | {t['class']} | `{t['formula']}` | {t['reason']} | {t['value']} |")
        a("")
        a(f"- cancels: {', '.join(arm['cancels'])}")
        a(f"- cancels only under the stated condition: {', '.join(arm['cancels_conditionally'])}")
        a(f"- does not cancel: {', '.join(arm['does_not_cancel'])}")
        a(f"- overhead for the break-even relations: {arm['overhead_for_breakeven']}")
        a(f"- sourced lower bound: {arm['sourced_lower_bound']}")
        a("")
    a("## 5. Start-up vs steady")
    a("")
    su = doc["startup"]
    a(f"Phase order ({su['phase_order_status']}):")
    a("")
    a("| phase | components on | lower bound on bus draw (all architectures) |")
    a("|---|---|---|")
    for ph in su["phase_order"]:
        lb = su["phase_bus_lower_bounds_all_architectures"][ph["phase"]]
        v = lb["P_bus_W_at_least"]
        a(f"| {ph['phase']} | {', '.join(ph['on'])} | {('≥ ' + _fmt_range(v) + ' W') if isinstance(v, list) else v} ({lb['from']}) |")
    a("")
    for k, v in su["differential"].items():
        a(f"- **{k}**: {v}")
    a(f"- start-up peak limit: {su['peak_limit']['value_W']} W, {su['peak_limit']['status']} ({su['peak_limit']['note']})")
    a(f"- {su['startup_ledger']}")
    a("")
    a("## 6. Headroom inside the RFP < 1.5 kW (conditional, symbolic)")
    a("")
    hr = doc["headroom"]
    a(f"Limit {hr['limit_W']} W ({hr['limit_status']}; {hr['limit_source']}). Open scope readings: "
      + "; ".join(hr["scope_open"]) + ".")
    a("")
    for k, v in hr["inequalities"].items():
        a(f"- {k}: `{v}`")
    a(f"- {hr['discharge_allowance_coefficient']}")
    a(f"- {hr['measured_point_table_note']}")
    a(f"- {hr['numeric_headroom']}")
    a("")
    a("## 7. What each TBD needs")
    a("")
    a("| component | item | requires | blocking lane / measurement |")
    a("|---|---|---|---|")
    for t in doc["tbd_register"]:
        a(f"| `{t['component']}` | {t['item']} | {t['requires']} | {t['blocking']} |")
    a("")
    a("## 8. Milestones")
    a("")
    ms = doc["milestones"]
    a(f"- **Supports:** {', '.join(ms['supports'])}. {ms['A']}.")
    a("- **To reach B:** " + "; ".join(ms["to_reach_B"]) + ".")
    a("- **To reach C:** " + "; ".join(ms["to_reach_C"]) + ".")
    a("")
    a("## 9. Owner questions (thresholds not in the RFP are PROPOSED)")
    a("")
    for q in doc["owner_questions"]:
        a(f"- {q}")
    a("")
    a("## 10. Inputs (pinned by sha256; a missing or changed input stops the build)")
    a("")
    a("| key | path | lane | lane commit | sha256 |")
    a("|---|---|---|---|---|")
    for p in doc["inputs"]:
        a(f"| {p['key']} | `{p['path']}` | {p['lane']} | {(p['lane_commit'] or '—')[:10]} | `{p['sha256'][:16]}…` |")
    a("")
    a("Not used: " + " / ".join(doc["not_used"]))
    a("")
    a("Self-checks: " + "; ".join(f"{k}: {'pass' if v['pass'] else 'FAIL'}" for k, v in doc["self_checks"].items()))
    a("")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare byte for byte")
    args = ap.parse_args(argv)
    doc = build()
    js, md = dump_json(doc), render_md(doc)
    if args.check:
        bad = []
        for path, text in ((OUT_JSON, js), (OUT_MD, md)):
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() != text:
                        bad.append(os.path.basename(path))
            except FileNotFoundError:
                bad.append(os.path.basename(path) + " (missing)")
        if bad:
            print("DRIFT: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("OK: aux_bus_comparison_v1 reproduces byte for byte")
        return 0
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(js)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {os.path.relpath(OUT_JSON, ROOT)} and {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
