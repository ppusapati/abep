"""Bus-power boundary v2 for the parallel RF || Hall investigation.

``bus_power_boundary_v1`` (abep_sim/arch_boundary.py) is untouched and stays the boundary of the v1 architectures
(hall_only / rf_hall = RF -> Hall pre-ionization / ecr_hall). v2 defines a separate boundary for the installed
architectures rf_only, hall_only and rf_hall_parallel:

    P_bus = sum_i P_load,i / eta_i        (every installed component listed explicitly, nothing defaulted)

Component groups
  common : compressor, atmospheric_flow_control, xe_flow_control, thermal_control, housekeeping
  rf     : rf_source, rf_magnet
  hall   : hall_discharge, hall_magnet, cathode_keeper, cathode_heater

rf_hall_parallel requires the complete universe. Components of a branch that the operating mode does not enable
must be passed as exactly 0 W with efficiency 1 (genuinely unpowered); any power on a disabled branch raises
(inactive components may not consume hidden power). A load given as ``TBD`` makes the ledger INCOMPLETE_EVIDENCE:
the total is not reported, only the known lower bound.

OFF-mode policy: common components (compressor, flow control, thermal control, housekeeping) are caller-stated in
EVERY mode including OFF (standby heaters, controller, plenum filling may draw power); v2 never assumes them zero.
xe_flow_control must be exactly 0 W / efficiency 1 when no Xe system is installed.

RF load plane: net RF power (forward minus reflected) at the antenna/coupler feed terminal of the standalone RF
thruster. Generator, matching network, filters and harness are inside the bus-to-load efficiency. Hall load planes
keep the v1 terminology. rf_magnet: RF magnetic-nozzle / source coil terminals (0 W, efficiency 1 for a permanent
magnet, passed explicitly).
"""
from __future__ import annotations

import math
from typing import Mapping

from .parallel_contracts import (BALANCE_REL_TOL, ContractError, Quantity, Status, TBD, real, serialise)
from .propulsion_modes import ArchitectureKind, IllegalModeError, InstalledArchitecture, mode_spec

BOUNDARY_VERSION = "bus_power_boundary_v2"

COMMON = ("compressor", "atmospheric_flow_control", "xe_flow_control", "thermal_control", "housekeeping")
RF = ("rf_source", "rf_magnet")
HALL = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater")
BRANCH_OF = {**{c: "common" for c in COMMON}, **{c: "rf" for c in RF}, **{c: "hall" for c in HALL}}

REQUIRED_COMPONENTS = {
    ArchitectureKind.RF_ONLY: COMMON + RF,
    ArchitectureKind.HALL_ONLY: COMMON + HALL,
    ArchitectureKind.RF_HALL_PARALLEL: COMMON + RF + HALL,
}
_FROZEN = {k: tuple(v) for k, v in REQUIRED_COMPONENTS.items()}

COMPONENT_DEFINITIONS = {
    "compressor": "electrical input of the compressor motor drive (motor, bearings, drive losses inside the load).",
    "atmospheric_flow_control": "atmospheric-path metering valve / flow-controller terminals.",
    "xe_flow_control": "Xe-path regulator, latch and proportional valve / flow-controller terminals (0 W, eff 1 when "
                       "no Xe system is installed or it is unpowered).",
    "thermal_control": "propulsion-subsystem heaters and active thermal hardware drawn from the bus.",
    "housekeeping": "propulsion controller, PPU control electronics, sensors and telemetry interface.",
    "rf_source": "net RF power (forward minus reflected) at the standalone RF thruster's antenna/coupler feed "
                 "terminal; generator, matching network, filters and harness inside the efficiency.",
    "rf_magnet": "RF source / magnetic-nozzle coil terminals (I^2 R); 0 W, efficiency 1 for permanent magnets.",
    "hall_discharge": "anode-cathode terminals at the Hall thruster (V_d x I_d, time-averaged); v1 terminology.",
    "hall_magnet": "Hall electromagnet coil terminals (I^2 R); 0 W, efficiency 1 for permanent magnets.",
    "cathode_keeper": "Hall cathode keeper terminals.",
    "cathode_heater": "Hall cathode heater terminals in the evaluated mode (0 W, efficiency 1 when off/heaterless).",
}

COMPONENT_GROUPS = {
    "common_feed": ("compressor", "atmospheric_flow_control", "xe_flow_control"),
    "common_controls_thermal": ("thermal_control", "housekeeping"),
    "rf": RF,
    "hall": HALL,
}


def _num(v, what: str):
    """A load or efficiency: a number, a Quantity (value used, evidence kept) or TBD (returned as is)."""
    if isinstance(v, TBD):
        return v, None
    if isinstance(v, Quantity):
        return real(v.value, what), v
    return real(v, what), None


def ledger(architecture: InstalledArchitecture, mode, loads: Mapping, efficiencies: Mapping) -> dict:
    """Bus-power ledger of one operating point. ``loads`` / ``efficiencies`` must contain exactly the installed
    architecture's components. Returns a dict (see bus_power_v2.schema.json)."""
    if not isinstance(architecture, InstalledArchitecture):
        raise ContractError("architecture must be an InstalledArchitecture")
    spec = architecture.check_mode(mode)
    required = _FROZEN[architecture.kind]
    if tuple(REQUIRED_COMPONENTS[architecture.kind]) != required:
        raise RuntimeError(f"REQUIRED_COMPONENTS[{architecture.kind.value}] was modified at runtime; "
                           f"{BOUNDARY_VERSION} is frozen")
    for name, m in (("loads", loads), ("efficiencies", efficiencies)):
        if not isinstance(m, Mapping):
            raise ContractError(f"{name} must be a mapping component -> value")
        keys = set(m)
        missing = [c for c in required if c not in keys]
        extra = sorted(str(k) for k in keys if k not in required)
        if missing or extra:
            raise ContractError(f"{name} for {architecture.kind.value} must have exactly {list(required)} "
                                f"({BOUNDARY_VERSION}); missing {missing}, extra {extra}")

    enabled = {"common": True, "rf": spec.rf_enabled, "hall": spec.hall_enabled}
    items, missing_evidence = [], []
    for comp in required:
        p, p_ev = _num(loads[comp], f"load of {comp!r}")
        eta, eta_ev = _num(efficiencies[comp], f"efficiency of {comp!r}")
        branch = BRANCH_OF[comp]
        if comp == "xe_flow_control" and not architecture.xe_system_installed:
            if isinstance(p, TBD) or isinstance(eta, TBD) or p != 0.0 or eta != 1.0:
                raise IllegalModeError("xe_flow_control must be 0 W / efficiency 1 when no Xe system is installed")
        if not enabled[branch]:
            if isinstance(p, TBD) or isinstance(eta, TBD) or p != 0.0 or eta != 1.0:
                raise IllegalModeError(f"{comp!r} belongs to the {branch} branch, which mode {spec.mode.value} does "
                                       "not enable: it must be passed as exactly 0 W with efficiency 1 "
                                       "(inactive components may not consume hidden power)")
        if not isinstance(p, TBD) and p < 0.0:
            raise ContractError(f"load of {comp!r} must be >= 0 W, got {p!r}")
        if not isinstance(eta, TBD) and not (0.0 < eta <= 1.0):
            raise ContractError(f"efficiency of {comp!r} must be in (0, 1], got {eta!r}")
        item = {"component": comp, "branch": branch, "active": enabled[branch],
                "P_load_W": serialise(p), "efficiency": serialise(eta),
                "load_evidence": serialise(p_ev), "efficiency_evidence": serialise(eta_ev)}
        if isinstance(p, TBD) or isinstance(eta, TBD):
            missing_evidence.append(comp)
            item.update(P_bus_W=None, P_loss_W=None)
        else:
            pb = p / eta
            if not math.isfinite(pb):
                raise ContractError(f"bus draw of {comp!r} overflows")
            item.update(P_bus_W=pb, P_loss_W=pb - p)
        items.append(item)

    known = [it for it in items if it["P_bus_W"] is not None]
    src = math.fsum(it["P_bus_W"] for it in known)
    dst = math.fsum(it["P_load_W"] for it in known) + math.fsum(it["P_loss_W"] for it in known)
    residual = dst - src
    if abs(residual) > BALANCE_REL_TOL * max(src, 1.0):
        raise RuntimeError(f"conservation gate failed: residual {residual!r} W ({BOUNDARY_VERSION})")
    groups = {}
    for g, comps in COMPONENT_GROUPS.items():
        sel = [it for it in items if it["component"] in comps]
        if not sel:
            continue
        groups[g] = (None if any(it["P_bus_W"] is None for it in sel)
                     else math.fsum(it["P_bus_W"] for it in sel))
    complete = not missing_evidence
    return {"boundary_version": BOUNDARY_VERSION, "architecture": architecture.kind.value, "mode": spec.mode.value,
            "status": Status.PASS.value if complete else Status.INCOMPLETE_EVIDENCE.value,
            "P_bus_W": dst if complete else None,
            "P_bus_known_lower_bound_W": dst,
            "missing_evidence": missing_evidence, "group_P_bus_W": groups,
            "items": items, "residual_W": residual}


# --------------------------------------------------------------------------------------- proposed allocations

ALLOCATION_STATUS = "PROPOSED_ENGINEERING_ALLOCATION"
PROPOSED_ALLOCATIONS = {
    "status": ALLOCATION_STATUS,
    "source": "ABEP Parallel RF-Hall Simulation v2 specification sec. 18 (owner-supplied investigation values)",
    "note": ("Design allocations, not physics and not evidence that any architecture meets them. The hard external "
             "requirement is P_bus < 1500 W (RFP). The specification lists P_common <= 300 W and 'common "
             "controls/thermal ~ 50 W' separately; v2 books them as the groups common_feed and "
             "common_controls_thermal (sum 1350 W with RF 700 W and Hall 300 W). Whether the 300 W already includes "
             "controls/thermal is an owner clarification."),
    "limits_W": {"P_design_total": 1350.0, "common_feed": 300.0, "rf": 700.0, "hall": 300.0,
                 "common_controls_thermal": 50.0},
    "frozen_before_results": True,
}


def allocation_report(result: dict, allocations: dict = PROPOSED_ALLOCATIONS) -> dict:
    """Compare a ledger with the PROPOSED allocations. A report, not a feasibility gate; the hard gate is the RFP."""
    lim = allocations["limits_W"]
    rep = {"status": allocations["status"], "groups": {}}
    for g, p in result["group_P_bus_W"].items():
        rep["groups"][g] = {"P_bus_W": p, "allocation_W": lim.get(g),
                            "within": None if p is None or g not in lim else p <= lim[g]}
    tot = result["P_bus_W"]
    rep["total"] = {"P_bus_W": tot, "allocation_W": lim["P_design_total"],
                    "within": None if tot is None else tot <= lim["P_design_total"]}
    return rep
