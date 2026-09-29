"""A9 spacecraft-DC propulsion bus-power boundary  (bus_power_boundary_a9_v1).

Owner decision A9 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json, status
OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE) and the owner answers
(docs/decisions/OD_2026_09_29_owner_answers_147.json, cited below as "row N"). A NEW boundary version: the historical
``abep_sim/arch_boundary.py`` (bus_power_boundary_v1) is untouched and is not imported here (rows 66, 108).

ONE electrical boundary -- the spacecraft-side DC input of the propulsion subsystem -- for the two A9 configurations
``hall_c1_reference`` (Hall + heated Xe-fed LaB6 C1, control/fallback) and ``hall_icp_neutralizer`` (Hall + downstream
13.56 MHz RF ICP electron source / neutralizer). Every active load has its own slot (row 110); legitimate loads are
never prohibited, they get an explicit slot (row 66).

Pure module: standard library only, no physics, no I/O, not wired into ``archengine`` (wiring it would be a model
change). It predicts nothing: no thrust, discharge current, neutralizer current or plasma state is computed; every
load and efficiency is a caller input carrying an evidence class and a source. **No default loads or efficiencies
exist anywhere in this module**; a missing installed slot raises, an unknown value is passed explicitly as ``"TBD"``
with what it requires, and the ledger then reports an incomplete status with only a known lower bound (rule 3).

Conventions (per slot, see ``SLOTS``):
  * ``P_W`` of a load record: power at the slot's load-side reference plane (time-averaged over the evaluated step).
    For ``icp_rf_source`` the load plane is the RF generator's DC input: only that DC input crosses the bus boundary.
    Forward, reflected and delivered RF power are MEASUREMENT quantities (``rf_power_planes``; row 72: directional
    coupler primary, calorimetry cross-check) and are refused as a bus load.
  * efficiency record ``value``: supply efficiency from the internal propulsion bus (``path = "internal_bus"``) or
    from the spacecraft input (``path = "direct"``) to the load plane, in (0, 1].
  * ``front_end``: the configurable spacecraft-input -> regulated internal propulsion bus converter (100 V for the
    breadboard, row 111); its efficiency divides every ``internal_bus`` slot.
  * ``P_bus_W = P_W / (eta_slot * eta_front_end)`` for internal-bus slots, ``P_W / eta_slot`` for direct slots.
  * The residual check is a bookkeeping identity (it catches floating-point error, not physics); an independent check
    needs a measured spacecraft-side bus current and voltage.
Allocations used by the checks (1350 W design allocation row 109; 300 W common allocation incl. the 50 W
controls/thermal allowance row 114) are OWNER ALLOCATIONS, never predictions and never gates.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real

BOUNDARY_VERSION = "bus_power_boundary_a9_v1"
V1_BOUNDARY_VERSION = "bus_power_boundary_v1"   # historical, read/cited only (abep_sim/arch_boundary.py, byte-identical)
CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")

# ---------------------------------------------------------------------------------------------- owner-given numbers
P_BUS_REQUIREMENT_W = 1500.0          # RFP '< 1.5 kW', strict, spacecraft-DC propulsion boundary incl. start-up (row 108)
DESIGN_ALLOCATION_W = 1350.0          # internal ~1.35 kW design allocation (row 109); owner allocation, not a gate
A5_ALLOCATION_RANGE_W = (1300.0, 1350.0)   # A5 'bus-power design allocation <= 1.30-1.35 kW' (context only)
COMMON_ALLOCATION_W = 300.0           # proposed 300 W common allocation, upper design allocation (row 114)
CONTROLS_THERMAL_ALLOWANCE_W = 50.0   # included inside the 300 W common allocation (row 114)
INTERNAL_BUS_V = 100.0                # regulated internal propulsion bus, breadboard/PPU architecture (row 111)
RF_FREQUENCY_HZ = 13.56e6             # row 72 / A9 decision
LAB_RF_FORWARD_W_RANGE = (0.0, 500.0) # laboratory source + inline chain sizing (row 72); not a flight allocation
C1_KEEPER_PULSE_IGNITION_CLASS_V = (300.0, 600.0)  # current-limited pulsed keeper ignition capability (row 89)

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation")
PATHS = ("internal_bus", "direct")
TBD = "TBD"

# ------------------------------------------------------------------------------------------------------ slots
# group: hall | c1 | icp | common | variant | reserved.  common_allocation: counted in the row-114 300 W allocation
# (PROPOSED composition, OQ-A902-02); controls_thermal: counted in the 50 W allowance.
SLOTS = {
    "hall_discharge": {
        "group": "hall", "rows": [110],
        "load_plane": "anode-cathode(-common) terminals at H-1, V_d x I_d time-averaged; discharge supply fed from the "
                      "internal bus"},
    "hall_magnet_inner": {
        "group": "hall", "rows": [110],
        "load_plane": "inner-coil terminals (I^2 R), current-controlled supply per coil (H2-1 H21-27)"},
    "hall_magnet_outer": {
        "group": "hall", "rows": [110],
        "load_plane": "outer-coil terminals (I^2 R), current-controlled supply per coil (H2-1 H21-27)"},
    "hall_magnet_trim": {
        "group": "hall", "rows": [110],
        "load_plane": "trim-coil terminals (I^2 R), current-controlled supply per coil (H2-1 H21-27); passed as 0 W "
                      "explicitly when the trim coil is unpowered"},
    "c1_heater": {
        "group": "c1", "rows": [110, 112],
        "load_plane": "C1 heater terminals in the evaluated step; reduced/disabled only after keeper/discharge are "
                      "stable per cathode procedure (row 112)"},
    "c1_keeper": {
        "group": "c1", "rows": [89, 110],
        "load_plane": "C1 keeper terminals; includes the current-limited pulsed ignition (300-600 V class, row 89) as a "
                      "start-up transient with recorded pulse energy"},
    "c1_common_tie": {
        "group": "c1", "rows": [91],
        "load_plane": "DC bus draw of the isolated, selectable cathode-common/bleeder network (selector, active bias "
                      "if selected, V/I measurement); the passively dissipated V x I across the tie is a measured "
                      "diagnostic supplied by the discharge circuit and is NOT added again (value TBD, row 91)"},
    "filter_getter": {
        "group": "c1", "rows": [51], "common_allocation": True,
        "load_plane": "Xe cathode-line filter/getter heater terminals (<= 17 W class only after vendor/spec "
                      "verification, row 51); C1/Xe branch only"},
    "icp_rf_source": {
        "group": "icp", "rows": [66, 72, 110],
        "load_plane": "13.56 MHz RF generator DC input terminals (the only RF-chain quantity crossing the bus "
                      "boundary); forward/reflected/delivered RF power are measurement quantities"},
    "icp_matching_network": {
        "group": "icp", "rows": [66, 110],
        "load_plane": "DC input of the matching network's tuning actuators/controller (0 W explicit for a fixed "
                      "passive match); RF loss inside the network is an RF-plane measurement quantity"},
    "icp_collector_bias": {
        "group": "icp", "rows": [70, 110],
        "load_plane": "electron-extraction collector/bias supply output (V_bias x I_collector); ICP body floating "
                      "unless the validated circuit requires otherwise (row 70)"},
    "icp_assist_magnet": {
        "group": "variant", "rows": [66, 69],
        "load_plane": "ICP assist-magnet coil terminals; present only in a declared variant (first build is "
                      "unmagnetized, row 69)"},
    "active_cooling": {
        "group": "variant", "rows": [66],
        "load_plane": "active cooling hardware (pump/fan/TEC) terminals; present only in a declared variant"},
    "flow_control_atmospheric": {
        "group": "common", "rows": [110], "common_allocation": True,
        "load_plane": "atmospheric-path metering/isolation valve driver outputs"},
    "flow_control_xe": {
        "group": "common", "rows": [90, 110], "common_allocation": True,
        "load_plane": "Xe-path valve/flow-controller driver outputs (incl. the two series isolation valves, row 90)"},
    "flow_control_icp_feed": {
        "group": "icp", "rows": [46], "common_allocation": True,
        "load_plane": "ICP gas-feed valve/flow-controller driver outputs (gas species and source not yet booked, "
                      "A9 recorder flag row 46)"},
    "compressor": {
        "group": "common", "rows": [22], "common_allocation": True,
        "load_plane": "compressor motor-drive electrical input; TBD gives PARTIAL_BOUNDARY until the ICD supplies it "
                      "(row 22)"},
    "thermal_control": {
        "group": "common", "rows": [114], "common_allocation": True, "controls_thermal": True,
        "load_plane": "propulsion-subsystem heaters / active thermal control terminals in the evaluated step"},
    "housekeeping_controls": {
        "group": "common", "rows": [114], "common_allocation": True, "controls_thermal": True,
        "load_plane": "propulsion controller, PPU control electronics, sensors, telemetry/command interface"},
    "reserved_dc_port": {
        "group": "reserved", "rows": [110],
        "load_plane": "reserved DC port output; stated explicitly (0 W when unused)"},
}
ALL_SLOTS = tuple(SLOTS)

_HALL = ("hall_discharge", "hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim")
_COMMON = ("flow_control_atmospheric", "flow_control_xe", "compressor", "thermal_control", "housekeeping_controls")
BASE_SLOTS = {
    "hall_c1_reference": _HALL + ("c1_heater", "c1_keeper", "c1_common_tie", "filter_getter") + _COMMON
                         + ("reserved_dc_port",),
    "hall_icp_neutralizer": _HALL + ("icp_rf_source", "icp_matching_network", "icp_collector_bias",
                                     "flow_control_icp_feed") + _COMMON + ("reserved_dc_port",),
}
VARIANT_OPTIONS = {
    "hall_c1_reference": ("active_cooling",),
    "hall_icp_neutralizer": ("icp_assist_magnet", "active_cooling"),
}
PEAK_EVENTS = {  # start-up peak-class events and the slot each belongs to (row 112: avoid simultaneous peaks)
    "compressor_spinup": "compressor",
    "c1_heater_preheat": "c1_heater",
    "c1_keeper_ignition": "c1_keeper",
    "magnet_ramp": "hall_magnet_inner",
    "icp_rf_ignition": "icp_rf_source",
    "icp_collector_bias_on": "icp_collector_bias",
    "hall_discharge_ignition": "hall_discharge",
    "active_cooling_start": "active_cooling",
}
# Enforced orderings (physically necessary or owner rule); every other ordering in the templates is PROPOSED.
ENFORCED_ORDER = {
    "hall_c1_reference": (("c1_heater_preheat", "c1_keeper_ignition"), ("c1_keeper_ignition", "hall_discharge_ignition"),
                          ("magnet_ramp", "hall_discharge_ignition")),
    "hall_icp_neutralizer": (("icp_rf_ignition", "icp_collector_bias_on"), ("icp_rf_ignition", "hall_discharge_ignition"),
                             ("magnet_ramp", "hall_discharge_ignition")),
}
# PROPOSED start-up templates (revised SEQ-1, row 112): time-ordered, one peak-class event per step.
SEQUENCE_TEMPLATES = {
    "hall_c1_reference": (
        {"step_id": "C-S0", "name": "standby", "event": None, "on": ["housekeeping_controls", "thermal_control"]},
        {"step_id": "C-S1", "name": "compressor spin-up / plenum fill", "event": "compressor_spinup",
         "on": ["compressor", "flow_control_atmospheric"]},
        {"step_id": "C-S2", "name": "C1 Xe purge + heater preheat (Xe booked, row 42; dwell cap row 93)",
         "event": "c1_heater_preheat", "on": ["flow_control_xe", "filter_getter", "c1_heater"]},
        {"step_id": "C-S3", "name": "magnet ramp to setpoint", "event": "magnet_ramp",
         "on": ["hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim"]},
        {"step_id": "C-S4", "name": "keeper ignition (pulsed 300-600 V class, <= 120 s x 2 retries dwell, row 93)",
         "event": "c1_keeper_ignition", "on": ["c1_keeper", "c1_common_tie"]},
        {"step_id": "C-S5", "name": "Hall discharge ignition (heater still on)", "event": "hall_discharge_ignition",
         "on": ["hall_discharge"]},
        {"step_id": "C-S6", "name": "keeper/discharge stable -> heater reduced/disabled per cathode procedure",
         "event": None, "on": [], "requires_flags": ["keeper_stable", "discharge_stable"]},
        {"step_id": "C-S7", "name": "steady", "event": None, "on": [], "phase": "steady"},
    ),
    "hall_icp_neutralizer": (
        {"step_id": "I-S0", "name": "standby", "event": None, "on": ["housekeeping_controls", "thermal_control"]},
        {"step_id": "I-S1", "name": "compressor spin-up / plenum fill", "event": "compressor_spinup",
         "on": ["compressor", "flow_control_atmospheric"]},
        {"step_id": "I-S2", "name": "magnet ramp to setpoint", "event": "magnet_ramp",
         "on": ["hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim"]},
        {"step_id": "I-S3", "name": "ICP gas feed + RF ignition (no thermionic heater)", "event": "icp_rf_ignition",
         "on": ["flow_control_icp_feed", "icp_matching_network", "icp_rf_source"]},
        {"step_id": "I-S4", "name": "collector/bias on (electron extraction)", "event": "icp_collector_bias_on",
         "on": ["icp_collector_bias"]},
        {"step_id": "I-S5", "name": "Hall discharge ignition with ICP electrons (row 24)",
         "event": "hall_discharge_ignition", "on": ["hall_discharge"]},
        {"step_id": "I-S6", "name": "steady", "event": None, "on": [], "phase": "steady"},
    ),
}

_REL_TOL = 1e-12


class BoundaryA9Error(ValueError):
    """Malformed or refused input to the A9 boundary (no fallback, no default)."""


# ------------------------------------------------------------------------------------------------------ helpers
def _real(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise BoundaryA9Error(f"{what} must be a real number, got {type(value).__name__} {value!r}")
    x = float(value)
    if not math.isfinite(x):
        raise BoundaryA9Error(f"{what} must be finite, got {x!r}")
    return x + 0.0


def _nonempty(rec: Mapping, key: str, what: str) -> str:
    v = rec.get(key)
    if not isinstance(v, str) or not v.strip():
        raise BoundaryA9Error(f"{what}: '{key}' must be a non-empty string")
    return v


def installed_slots(config: str, variant: Sequence = ()) -> tuple:
    """Slots physically installed in ``config`` with the declared variant options (order of ``ALL_SLOTS``)."""
    if not isinstance(config, str) or config not in BASE_SLOTS:
        raise BoundaryA9Error(f"unknown configuration {config!r}; {BOUNDARY_VERSION} defines {list(CONFIGURATIONS)}")
    if isinstance(variant, str) or not isinstance(variant, Sequence):
        raise BoundaryA9Error("variant must be a sequence of option names (use () for the base configuration)")
    opts = list(variant)
    if len(set(opts)) != len(opts):
        raise BoundaryA9Error(f"duplicate variant option in {opts!r}")
    for o in opts:
        if o not in VARIANT_OPTIONS[config]:
            raise BoundaryA9Error(f"variant option {o!r} is not declared for {config!r} "
                                  f"(allowed {list(VARIANT_OPTIONS[config])}); a new variant needs a controlled change")
    s = set(BASE_SLOTS[config]) | set(opts)
    return tuple(c for c in ALL_SLOTS if c in s)


def _load_record(slot: str, rec) -> dict:
    what = f"load of {slot!r}"
    if not isinstance(rec, Mapping):
        raise BoundaryA9Error(f"{what} must be a record {{'P_W', 'evidence_class', 'source'}} or "
                              f"{{'P_W': 'TBD', 'tbd_requires'}}, got {type(rec).__name__}")
    if "P_W" not in rec:
        raise BoundaryA9Error(f"{what}: 'P_W' missing (no default)")
    if slot == "icp_rf_source":
        plane = rec.get("plane")
        if plane != "generator_dc_input":
            raise BoundaryA9Error(f"{what}: plane must be 'generator_dc_input' (got {plane!r}); only the RF generator "
                                  f"DC input crosses the bus boundary, forward/reflected/delivered RF power are "
                                  f"measurement quantities (row 72)")
    p = rec["P_W"]
    if isinstance(p, str):
        if p != TBD:
            raise BoundaryA9Error(f"{what}: string value must be exactly {TBD!r}, got {p!r}")
        return {"P_W": None, "tbd_requires": _nonempty(rec, "tbd_requires", what), "evidence_class": None,
                "source": None}
    x = _real(p, what)
    if x < 0.0:
        raise BoundaryA9Error(f"{what} must be >= 0 W, got {x!r}")
    ec = rec.get("evidence_class")
    if ec not in EVIDENCE_CLASSES:
        raise BoundaryA9Error(f"{what}: evidence_class must be one of {list(EVIDENCE_CLASSES)}, got {ec!r}")
    return {"P_W": x, "tbd_requires": None, "evidence_class": ec, "source": _nonempty(rec, "source", what)}


def _eff_record(what: str, rec, need_path: bool = True) -> dict:
    if not isinstance(rec, Mapping):
        raise BoundaryA9Error(f"{what} must be a record {{'value', 'evidence_class', 'source', 'path'}}, "
                              f"got {type(rec).__name__}")
    path = rec.get("path")
    if need_path and path not in PATHS:
        raise BoundaryA9Error(f"{what}: path must be one of {list(PATHS)}, got {path!r}")
    if "value" not in rec:
        raise BoundaryA9Error(f"{what}: 'value' missing (no default)")
    v = rec["value"]
    if isinstance(v, str):
        if v != TBD:
            raise BoundaryA9Error(f"{what}: string value must be exactly {TBD!r}, got {v!r}")
        return {"value": None, "path": path, "tbd_requires": _nonempty(rec, "tbd_requires", what),
                "evidence_class": None, "source": None}
    x = _real(v, what)
    if not (0.0 < x <= 1.0):
        raise BoundaryA9Error(f"{what} must be in (0, 1], got {x!r}")
    ec = rec.get("evidence_class")
    if ec not in EVIDENCE_CLASSES:
        raise BoundaryA9Error(f"{what}: evidence_class must be one of {list(EVIDENCE_CLASSES)}, got {ec!r}")
    return {"value": x, "path": path, "tbd_requires": None, "evidence_class": ec,
            "source": _nonempty(rec, "source", what)}


def _not_installed_ok(slot: str, loads: Mapping, effs: Mapping, config: str) -> None:
    if slot in loads:
        rec = loads[slot]
        p = rec.get("P_W") if isinstance(rec, Mapping) else rec
        if isinstance(p, bool) or not isinstance(p, Real) or float(p) != 0.0:
            raise BoundaryA9Error(f"slot {slot!r} is not installed in {config!r} with this variant; it may only be "
                                  f"omitted or passed as exactly 0 W (got {p!r}) - no hidden consumption")
    if slot in effs:
        rec = effs[slot]
        v = rec.get("value") if isinstance(rec, Mapping) else rec
        if isinstance(v, bool) or not isinstance(v, Real) or float(v) != 1.0:
            raise BoundaryA9Error(f"slot {slot!r} is not installed in {config!r}; its efficiency may only be omitted "
                                  f"or exactly 1 (got {v!r})")


# ------------------------------------------------------------------------------------------------------ ledger
def ledger(config: str, loads: Mapping, efficiencies: Mapping, front_end: Mapping, variant: Sequence = (),
           label: str = "") -> dict:
    """Spacecraft-side DC bus-power ledger of one configuration in one evaluated step.

    ``loads``/``efficiencies`` must contain every installed slot (``installed_slots(config, variant)``); slots that
    are not installed may be omitted or passed as exactly 0 W / efficiency 1 and are reported as ``NOT_INSTALLED``
    with exactly 0.0 W. ``front_end``: {'value', 'evidence_class', 'source'} or {'value': 'TBD', 'tbd_requires'}.

    Status: ``COMPLETE`` (P_bus known), ``PARTIAL_BOUNDARY`` (compressor draw TBD, row 22) or
    ``INCOMPLETE_EVIDENCE`` (another load or an efficiency TBD). When not complete, ``P_bus_W`` is None and
    ``P_bus_lower_bound_W`` is the rigorous lower bound (TBD loads count 0 W; a TBD efficiency counts 1).
    """
    inst = installed_slots(config, variant)
    if not isinstance(loads, Mapping):
        raise BoundaryA9Error(f"loads must be a mapping slot -> record, got {type(loads).__name__}")
    if not isinstance(efficiencies, Mapping):
        raise BoundaryA9Error(f"efficiencies must be a mapping slot -> record, got {type(efficiencies).__name__}")
    unknown = sorted(str(k) for k in set(loads) | set(efficiencies) if k not in SLOTS)
    if unknown:
        raise BoundaryA9Error(f"unknown slot(s) {unknown}; {BOUNDARY_VERSION} slots are {list(ALL_SLOTS)}")
    missing_l = [c for c in inst if c not in loads]
    missing_e = [c for c in inst if c not in efficiencies]
    if missing_l or missing_e:
        raise BoundaryA9Error(f"{config!r}{list(variant)!r}: installed slots need an explicit load and efficiency "
                              f"(no default); missing loads {missing_l}, missing efficiencies {missing_e}")
    fe = _eff_record("front_end efficiency", front_end, need_path=False)

    items, tbd = [], []
    for slot in ALL_SLOTS:
        if slot not in inst:
            _not_installed_ok(slot, loads, efficiencies, config)
            items.append({"slot": slot, "group": SLOTS[slot]["group"], "state": "NOT_INSTALLED", "P_W": 0.0,
                          "efficiency": 1.0, "path": None, "P_bus_W": 0.0, "P_loss_W": 0.0,
                          "evidence_class": None, "source": None})
            continue
        L = _load_record(slot, loads[slot])
        E = _eff_record(f"efficiency of {slot!r}", efficiencies[slot])
        eta_fe = fe["value"] if E["path"] == "internal_bus" else 1.0
        if L["P_W"] is None:
            tbd.append({"slot": slot, "what": "load", "requires": L["tbd_requires"]})
        if E["value"] is None and L["P_W"] != 0.0:   # an OFF slot (exactly 0 W) needs no efficiency value
            tbd.append({"slot": slot, "what": "efficiency", "requires": E["tbd_requires"]})
        if E["path"] == "internal_bus" and fe["value"] is None and L["P_W"] not in (None, 0.0):
            tbd.append({"slot": slot, "what": "front_end efficiency", "requires": fe["tbd_requires"]})
        if L["P_W"] == 0.0:
            p_bus, lb, state = 0.0, 0.0, "OFF"
        elif L["P_W"] is None:
            p_bus, lb, state = None, 0.0, "ON"
        else:
            state = "ON"
            lb = L["P_W"] / (E["value"] or 1.0) / (eta_fe or 1.0)
            p_bus = None if (E["value"] is None or eta_fe is None) else L["P_W"] / E["value"] / eta_fe
            if not math.isfinite(lb):
                raise BoundaryA9Error(f"bus draw of {slot!r} overflows")
        items.append({"slot": slot, "group": SLOTS[slot]["group"], "state": state, "P_W": L["P_W"],
                      "efficiency": E["value"], "path": E["path"], "P_bus_W": p_bus,
                      "P_loss_W": None if p_bus is None else p_bus - L["P_W"], "lower_bound_W": lb,
                      "evidence_class": L["evidence_class"], "source": L["source"],
                      "efficiency_evidence_class": E["evidence_class"], "efficiency_source": E["source"]})

    lower = math.fsum(it.get("lower_bound_W", 0.0) for it in items)
    if not math.isfinite(lower):
        raise BoundaryA9Error("total bus draw overflows")
    if any(t["slot"] == "compressor" and t["what"] == "load" for t in tbd):
        status = "PARTIAL_BOUNDARY"
    elif tbd:
        status = "INCOMPLETE_EVIDENCE"
    else:
        status = "COMPLETE"
    p_total, residual = None, None
    if status == "COMPLETE":
        source_total = math.fsum(it["P_bus_W"] for it in items)
        dest_total = math.fsum(it["P_W"] for it in items if it["P_W"]) + math.fsum(it["P_loss_W"] for it in items)
        residual = dest_total - source_total
        if abs(residual) > _REL_TOL * max(source_total, 1.0):
            raise RuntimeError(f"bookkeeping identity failed: residual {residual!r} W ({BOUNDARY_VERSION})")
        p_total = dest_total
    classes = sorted({it["evidence_class"] for it in items if it["evidence_class"]})
    return {"boundary_version": BOUNDARY_VERSION, "configuration": config, "variant": list(variant),
            "label": label, "status": status, "P_bus_W": p_total, "P_bus_lower_bound_W": lower,
            "residual_W": residual, "tbd": tbd, "load_evidence_classes": classes,
            "measured_only": classes == ["measured"],
            "front_end": {"efficiency": fe["value"], "evidence_class": fe["evidence_class"], "source": fe["source"],
                          "internal_bus_V": INTERNAL_BUS_V},
            "items": items}


def _group_sum(led: dict, key: str):
    its = [it for it in led["items"] if SLOTS[it["slot"]].get(key) and it["state"] != "NOT_INSTALLED"]
    known = all(it["P_bus_W"] is not None for it in its)
    return (math.fsum(it["P_bus_W"] for it in its) if known else None,
            math.fsum(it.get("lower_bound_W", 0.0) for it in its))


# ------------------------------------------------------------------------------------------------------ checks
def _verdict_below(value, lower, limit, strict: bool, ok: str, bad: str) -> str:
    if value is not None:
        return ok if ((value < limit) if strict else (value <= limit)) else bad
    if (lower >= limit) if strict else (lower > limit):
        return bad
    return "NOT_EVALUABLE"


def rfp_power_gate(steady: dict, startup_steps: Sequence) -> dict:
    """RFP gate P_bus < 1500 W applied to the steady ledger AND every start-up step (row 108).

    PASS only if every ledger is COMPLETE and below the limit; FAIL if any known total or any lower bound reaches
    the limit; otherwise NOT_EVALUABLE. An empty start-up list is refused (the gate covers transients).
    """
    if isinstance(startup_steps, (str, Mapping)) or not isinstance(startup_steps, Sequence) or not startup_steps:
        raise BoundaryA9Error("rfp_power_gate needs a non-empty sequence of start-up step ledgers (row 108: start-up "
                              "transients stay below 1.5 kW unless the official RFP allows an exception)")
    rows = []
    for role, led in [("steady", steady)] + [("startup", s) for s in startup_steps]:
        if not isinstance(led, Mapping) or led.get("boundary_version") != BOUNDARY_VERSION:
            raise BoundaryA9Error(f"not a {BOUNDARY_VERSION} ledger: {led!r:.80}")
        v = _verdict_below(led["P_bus_W"], led["P_bus_lower_bound_W"], P_BUS_REQUIREMENT_W, True, "PASS", "FAIL")
        rows.append({"role": role, "label": led["label"], "status": led["status"], "P_bus_W": led["P_bus_W"],
                     "P_bus_lower_bound_W": led["P_bus_lower_bound_W"], "verdict": v,
                     "measured_only": led["measured_only"]})
    vs = {r["verdict"] for r in rows}
    overall = "FAIL" if "FAIL" in vs else ("PASS" if vs == {"PASS"} else "NOT_EVALUABLE")
    return {"gate": "RFP P_bus < 1500 W (steady and start-up)", "limit_W": P_BUS_REQUIREMENT_W, "strict": True,
            "verdict": overall, "evidence_basis": "measured" if all(r["measured_only"] for r in rows)
            else "includes non-measured loads (not a demonstration)", "rows": rows}


def allocation_checks(led: dict) -> dict:
    """Owner-allocation checks (NOT gates, NOT predictions): design allocation 1350 W (row 109), the 300 W common
    allocation including the 50 W controls/thermal allowance (row 114)."""
    if not isinstance(led, Mapping) or led.get("boundary_version") != BOUNDARY_VERSION:
        raise BoundaryA9Error("allocation_checks needs a bus_power_boundary_a9_v1 ledger")
    c_val, c_lb = _group_sum(led, "common_allocation")
    t_val, t_lb = _group_sum(led, "controls_thermal")
    out = {"kind": "OWNER_ALLOCATION_CHECK (not a gate, not a prediction)",
           "design_allocation": {"limit_W": DESIGN_ALLOCATION_W, "row": 109,
                                 "verdict": _verdict_below(led["P_bus_W"], led["P_bus_lower_bound_W"],
                                                           DESIGN_ALLOCATION_W, False, "WITHIN_ALLOCATION",
                                                           "EXCEEDS_ALLOCATION")},
           "a5_lower_allocation": {"limit_W": A5_ALLOCATION_RANGE_W[0], "context_only": True,
                                   "verdict": _verdict_below(led["P_bus_W"], led["P_bus_lower_bound_W"],
                                                             A5_ALLOCATION_RANGE_W[0], False, "WITHIN_ALLOCATION",
                                                             "EXCEEDS_ALLOCATION")},
           "common_allocation": {"limit_W": COMMON_ALLOCATION_W, "row": 114, "P_bus_W": c_val,
                                 "P_bus_lower_bound_W": c_lb,
                                 "verdict": _verdict_below(c_val, c_lb, COMMON_ALLOCATION_W, False,
                                                           "WITHIN_ALLOCATION", "EXCEEDS_ALLOCATION")},
           "controls_thermal_allowance": {"allowance_W": CONTROLS_THERMAL_ALLOWANCE_W, "row": 114, "P_bus_W": t_val,
                                          "P_bus_lower_bound_W": t_lb,
                                          "verdict": _verdict_below(t_val, t_lb, CONTROLS_THERMAL_ALLOWANCE_W, False,
                                                                    "WITHIN_ALLOWANCE", "EXCEEDS_ALLOWANCE")}}
    return out


def rf_power_planes(P_dc_in_W, P_forward_W, P_reflected_W, P_delivered_W, u_W) -> dict:
    """RF power planes of the ICP source (row 72). Only the generator DC input crosses the bus boundary.

    Forward/reflected come from the directional coupler (primary); delivered-to-load from an independent method
    (calorimetry cross-check) or ``"TBD"``. ``u_W`` is the caller's explicit measurement tolerance used only to
    refuse physically impossible orderings (reflected > forward, forward > DC input, delivered > net forward).
    """
    u = _real(u_W, "u_W")
    if u < 0.0:
        raise BoundaryA9Error("u_W must be >= 0")
    dc = _real(P_dc_in_W, "P_dc_in_W")
    fw = _real(P_forward_W, "P_forward_W")
    rf = _real(P_reflected_W, "P_reflected_W")
    for n, x in (("P_dc_in_W", dc), ("P_forward_W", fw), ("P_reflected_W", rf)):
        if x < 0.0:
            raise BoundaryA9Error(f"{n} must be >= 0")
    if rf > fw + u:
        raise BoundaryA9Error("reflected power exceeds forward power beyond the stated tolerance")
    if fw > dc + u:
        raise BoundaryA9Error("forward RF power exceeds the generator DC input beyond the stated tolerance")
    net = fw - rf
    if isinstance(P_delivered_W, str):
        if P_delivered_W != TBD:
            raise BoundaryA9Error(f"P_delivered_W string must be exactly {TBD!r}")
        dl = None
    else:
        dl = _real(P_delivered_W, "P_delivered_W")
        if dl < 0.0 or dl > net + u:
            raise BoundaryA9Error("delivered power must be in [0, forward - reflected] within the stated tolerance")
    return {"bus_crossing_W": dc, "bus_crossing_plane": "generator_dc_input",
            "measurement_only": {"forward_W": fw, "reflected_W": rf, "net_forward_W": net, "delivered_W": dl},
            "derived": {"generator_dc_to_forward": (fw / dc) if dc > 0 else None,
                        "reflection_fraction": (rf / fw) if fw > 0 else None,
                        "match_and_line_loss_W": None if dl is None else net - dl}}


def check_startup_sequence(config: str, steps: Sequence, front_end: Mapping, variant: Sequence = ()) -> dict:
    """Evaluate a time-ordered start-up sequence (revised SEQ-1, row 112) and the transient RFP gate (row 108).

    ``steps``: list of {'step_id', 'event' (a PEAK_EVENTS key or None), 'loads', 'efficiencies', optional 'flags'
    {'keeper_stable', 'discharge_stable'}, optional 'phase' ('steady' only on the last step)}. The last step must be
    the steady step. Rule violations (simultaneous peak events, forbidden heater reduction, enforced order) are
    reported, not raised; malformed input raises.
    """
    inst = installed_slots(config, variant)
    if isinstance(steps, (str, Mapping)) or not isinstance(steps, Sequence) or len(steps) < 2:
        raise BoundaryA9Error("a start-up sequence needs at least one start-up step and a final steady step")
    ledgers, violations, seen_events, ids = [], [], {}, set()
    heater_was_on, heater_prev = False, None
    for i, st in enumerate(steps):
        if not isinstance(st, Mapping):
            raise BoundaryA9Error(f"step {i} must be a mapping")
        sid = _nonempty(st, "step_id", f"step {i}")
        if sid in ids:
            raise BoundaryA9Error(f"duplicate step_id {sid!r}")
        ids.add(sid)
        phase = st.get("phase")
        if (phase == "steady") != (i == len(steps) - 1):
            raise BoundaryA9Error("exactly the last step must carry phase 'steady'")
        ev = st.get("event")
        events = [] if ev is None else (list(ev) if isinstance(ev, (list, tuple)) else [ev])
        for e in events:
            if e not in PEAK_EVENTS:
                raise BoundaryA9Error(f"step {sid!r}: unknown event {e!r}; allowed {sorted(PEAK_EVENTS)}")
            if PEAK_EVENTS[e] not in inst:
                raise BoundaryA9Error(f"step {sid!r}: event {e!r} needs slot {PEAK_EVENTS[e]!r}, not installed in "
                                      f"{config!r}")
            seen_events.setdefault(e, i)
        if len(events) > 1:
            violations.append({"step_id": sid, "rule": "one peak-class event per step (row 112)",
                               "detail": events})
        led = ledger(config, st.get("loads"), st.get("efficiencies"), front_end, variant, label=sid)
        ledgers.append(led)
        if "c1_heater" in inst:
            h = next(it for it in led["items"] if it["slot"] == "c1_heater")["P_W"]
            flags = st.get("flags") or {}
            if heater_was_on and h is not None and heater_prev is not None and h < heater_prev:
                if not (flags.get("keeper_stable") is True and flags.get("discharge_stable") is True):
                    violations.append({"step_id": sid, "rule": "C1 heater reduced/disabled only after keeper and "
                                       "discharge are stable per cathode procedure (row 112)",
                                       "detail": {"from_W": heater_prev, "to_W": h}})
            if h:
                heater_was_on = True
            heater_prev = h
    for a, b in ENFORCED_ORDER[config]:
        if a in seen_events and b in seen_events and not seen_events[a] < seen_events[b]:
            violations.append({"step_id": steps[seen_events[b]]["step_id"], "rule": f"{a} before {b}",
                               "detail": {a: seen_events[a], b: seen_events[b]}})
        if b in seen_events and a not in seen_events:
            violations.append({"step_id": steps[seen_events[b]]["step_id"], "rule": f"{a} before {b}",
                               "detail": f"{a} missing"})
    gate = rfp_power_gate(ledgers[-1], ledgers[:-1])
    return {"boundary_version": BOUNDARY_VERSION, "configuration": config, "variant": list(variant),
            "sequence_status": "SEQUENCE_RULE_VIOLATION" if violations else "RULES_SATISFIED",
            "violations": violations, "transient_gate": gate,
            "steady_allocation_checks": allocation_checks(ledgers[-1]),
            "steps": [{"step_id": led["label"], "status": led["status"], "P_bus_W": led["P_bus_W"],
                       "P_bus_lower_bound_W": led["P_bus_lower_bound_W"]} for led in ledgers]}
