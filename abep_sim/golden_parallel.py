"""Golden regression vectors for the parallel RF || Hall v2 code (abep_sim/data/golden_parallel_v1.json).

PURPOSE: software reproducibility, conservation, schema stability and regression detection ONLY. The inputs are
TEST FIXTURES (evidence class 'assumed', validation_status TEST_FIXTURE); the outputs are NOT physical validation
evidence about any RF or Hall hardware and must never be quoted as performance.

The existing goldens (abep_sim/data/golden_v1.json, ``python -m abep_sim.golden``) are untouched.

    python -m abep_sim.golden_parallel generate   # intentional regeneration only (log it in docs/HISTORY.md)
    python -m abep_sim.golden_parallel check      # exit 0 when every vector reproduces
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import bus_power_v2, rf_reduced as R
from .hall_branch_adapter import POINT_EVIDENCE, HallBranchConfig, HallPoint
from .mass_bom_v2 import installed_items, rollup
from .parallel_contracts import FeedState, Quantity, TBD, investigation_constraints, pure_xe_feed
from .parallel_system import CommonState, HallCommand, RFCommand, evaluate
from .propellant_router import FlowRequest, XeSupply, route
from .propulsion_modes import InstalledArchitecture, Mode
from .rf_branch import RFBranchConfig
from .xe_mission_v2 import XeMissionLedger

GOLDEN_FILE = os.path.join(os.path.dirname(__file__), "data", "golden_parallel_v1.json")
REL_TOL = 1e-9
DISCLAIMER = ("software reproducibility / conservation / schema-stability vectors from TEST FIXTURES; NOT physical "
              "validation evidence")


def _q(v, u):
    return Quantity(v, u, "assumed", "golden_parallel fixture", "n/a", "regression only", "TEST_FIXTURE")


def _fixtures():
    air = FeedState(1.5e-6, 0.3, 300.0, {"O": 0.3, "O2": 0.2, "N2": 0.5, "N": 0.0, "Xe": 0.0},
                    "golden fixture", "assumed", "n/a", "regression only", "TEST_FIXTURE")
    xes = XeSupply(2.0e-6, 5.0, 2e5, 293.0, "golden fixture", "assumed", "n/a", "regression only", "TEST_FIXTURE")
    ch = R.RFChamberSpec(_q(3e-4, "m^3"), _q(0.03, "m^2"), _q(3e-3, "m^2"), _q(500.0, "K"), _q(0.4, "1"),
                         _q(0.3, "1"), _q(0.7, "1"), "golden-chamber")
    cp = R.RFCoupling(_q(13.56e6, "Hz"), _q(0.85, "1"), _q(0.8, "1"), TBD("eta_generator", "fixture"),
                      TBD("P_reflected_W", "fixture"), "golden-antenna")
    nz = R.RFNozzleSpec(_q(1.2, "1"), _q(2.0, "1"), _q(0.05, "T"), "golden-magnet", "fixture",
                        R.REFERENCE_DETACHMENT, R.REFERENCE_DIVERGENCE)
    rfc = RFBranchConfig(ch, cp, nz, _q(0.0, "W"), _q(1.0, "1"), (1.0, 0.0, 0.0), TBD("e", "f"), TBD("t", "f"))
    hc = HallBranchConfig(_q(0.93, "1"), _q(20.0, "W"), _q(0.8, "1"), _q(10.0, "W"), _q(0.8, "1"), _q(0.0, "W"),
                          _q(1.0, "1"), (1.0, 0.0, 0.0), TBD("e", "f"), TBD("t", "f"))
    hp = HallPoint("golden-point", "analog:golden-fixture", "xe", _q(1e-6, "kg/s"), _q(250.0, "W"), _q(250.0, "V"),
                   _q(0.015, "N"), _q(40.0, "deg"),
                   {"anode_mdot_kg_s": [0.9e-6, 1.1e-6], "P_discharge_W": [240.0, 260.0], "V_d_V": [240.0, 260.0]},
                   "golden fixture")
    common = CommonState({"compressor": 150.0, "atmospheric_flow_control": 5.0, "xe_flow_control": 5.0,
                          "thermal_control": 20.0, "housekeeping": 25.0}, {k: 0.9 for k in (
                          "compressor", "atmospheric_flow_control", "xe_flow_control", "thermal_control",
                          "housekeeping")})
    return air, xes, ch, cp, nz, rfc, hc, hp, common


def compute() -> dict:
    air, xes, ch, cp, nz, rfc, hc, hp, common = _fixtures()
    par = InstalledArchitecture("rf_hall_parallel", True)
    C = investigation_constraints(tuple(Mode))
    v = {}
    r = route(air, xes, Mode.RF_ATM_HALL_XE, FlowRequest(1.2e-6, 0.0, 0.0, 1e-6, 1e-8), par)
    v["router"] = {"unallocated_atm_kg_s": r.unallocated_atm_kg_s, "unallocated_xe_kg_s": r.unallocated_xe_kg_s}
    for Rm in (1.5, 2.0, 3.0):
        o = R.run(air, 700.0, ch, cp, R.RFNozzleSpec(nz.gamma, _q(Rm, "1"), nz.B0_T, nz.magnetic_geometry_id,
                                                     nz.topology_source, nz.detachment, nz.divergence), _q(0.0, "W"))
        v[f"rf_reduced_Rm{Rm}"] = {k: o[k] for k in ("Te_eV", "ne_m3", "utilization", "P_kinetic_W",
                                                     "P_kinetic_max_W", "thrust_N", "Isp_s",
                                                     "mass_balance_residual", "energy_balance_residual")}
        v[f"rf_reduced_Rm{Rm}"]["model_status"] = o["model_status"]
    o = R.run(air, 700.0, ch, cp, R.RFNozzleSpec(nz.gamma, _q(10.0, "1"), nz.B0_T, nz.magnetic_geometry_id,
                                                 nz.topology_source, nz.detachment, nz.divergence), _q(0.0, "W"))
    v["rf_reduced_Rm10_status"] = o["model_status"]
    s = evaluate(par, Mode.RF_ATM_HALL_XE, atm_feed=air, xe_supply=xes,
                 request=FlowRequest(1.5e-6, 0.0, 0.0, 1e-6, 1e-8), rf=RFCommand(700.0, rfc),
                 hall=HallCommand(250.0, 250.0, hc, POINT_EVIDENCE, points=(hp,)), common=common, constraints=C,
                 required_thrust_N=0.012)
    v["system_rf_atm_hall_xe"] = {k: s[k] for k in ("T_RF_N", "T_H_N", "T_total_axial_N", "P_RF_bus_W",
                                                    "P_H_bus_W", "P_common_bus_W", "P_total_bus_W",
                                                    "power_balance_residual_W", "mdot_xe_total_kg_s")}
    v["system_rf_atm_hall_xe"].update(status=s["status"], verdict=s["verdict"])
    led = XeMissionLedger(_q(5.0, "kg"))
    led.add_interval(0.0, 3600.0, Mode.RF_ATM, {})
    led.add_event(3600.0, "hall_startup", _q(3.6e-5, "kg"))
    led.add_interval(3600.0, 600.0, Mode.RF_ATM_HALL_XE, {"hall_xe_anode": 1e-6, "hall_cathode": 1e-7})
    sm = led.summary(reserve=_q(0.1, "1"), residual=_q(0.02, "1"))
    v["xe_mission"] = {k: sm[k] for k in ("xe_consumed_kg", "xe_total_required_kg", "hall_time_fraction")}
    cbe = {it["id"]: Quantity(1.0, "kg", "assumed", "golden fixture", "n/a", "regression only",
                              "ASSUMED_SCREENING_VALUE (TEST_FIXTURE)") for it in installed_items(par)}
    m = rollup(par, cbe, system_margin_fraction=0.2, constraints=C)
    v["mass_bom"] = {k: m[k] for k in ("cbe_dry_kg", "nominal_dry_kg", "system_margin_kg", "propellant_kg",
                                       "mev_kg")}
    v["bus_power_boundary"] = bus_power_v2.BOUNDARY_VERSION
    return v


def _close(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-18)
    return a == b


def generate(path: str = GOLDEN_FILE) -> dict:
    doc = {"golden": "golden_parallel_v1", "purpose": DISCLAIMER, "rel_tol": REL_TOL,
           "generator": "abep_sim/golden_parallel.py", "vectors": compute()}
    with open(path, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    return doc


def check(path: str = GOLDEN_FILE) -> list:
    ref = json.load(open(path))["vectors"]
    now = json.loads(json.dumps(compute()))
    return [k for k in ref if k not in now or not _close(ref[k], now[k])] + [k for k in now if k not in ref]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "generate":
        generate()
        print("written", GOLDEN_FILE)
    else:
        bad = check()
        print("OK" if not bad else f"MISMATCH: {bad}")
        sys.exit(1 if bad else 0)
