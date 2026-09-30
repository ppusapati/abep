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
  * ``P_W`` of a load record: power at the slot's load-side reference plane in the evaluated step. What the step
    value represents is declared per ledger as ``power_basis`` (``POWER_BASES``): ``steady_state``, ``step_average``,
    ``peak_sampled`` (unaveraged sampled peak) or ``p_bus_1ms_max``. The gate quantity is FROZEN by the owner
    (A9.1 OQ-A902-01; an A9 engineering definition pending authoritative RFP wording, not an ECSS requirement):
    P_bus,1ms,max = max_t (1/1 ms) integral_t^{t+1 ms} P_bus dtau < 1500 W for start-up AND steady state, measured at
    the spacecraft-DC propulsion boundary with synchronized channels, effective bandwidth >= 20 kHz, >= 100 kSa/s per
    relevant channel (or an equivalent direct bus-power channel) and documented anti-alias filtering
    (``GATE_DEFINITION``; ``p_bus_1ms_max()`` evaluates it from a sampled record). A ledger PASSes the gate only when
    declared ``p_bus_1ms_max`` AND it carries a ``gate_measurement`` conformance record meeting those requirements
    (A9-10 repair; the record is what makes the declared basis checkable). No step average may be substituted
    (A9.1). The unaveraged sampled peak (``peak_sampled``) is for protection analysis only, not the 1.5 kW gate
    (A9.1 OQ-A902-01): it never PASSes and never FAILs here (NOT_EVALUABLE); whether a conformant sampled peak below
    the limit may bound the 1 ms maximum is the OPEN owner question OQ-A910-03 and is not implemented before the owner
    rules. A FAIL needs a declared basis whose value bounds P_bus,1ms,max from below: ``p_bus_1ms_max`` itself, or
    ``step_average`` / ``steady_state``, which bound it only under the stated assumption that the averaging duration
    is a whole multiple of 1 ms or much longer than 1 ms (then the mean over the step cannot exceed the largest 1 ms
    mean; for a duration of a non-integer number of ms the bound is approximate). An unstated basis (None) gives
    NOT_EVALUABLE in both directions.
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
  * No-load / quiescent converter losses are NOT produced by the per-slot model: a slot at exactly 0 W output draws
    exactly 0 W (``P_W / eta``), even if its supply is energised. The standby draw of energised-but-idle supplies and
    of the front end must be booked explicitly in ``housekeeping_controls`` (as its measured or cited DC draw); it is
    otherwise excluded from the ledger. This is a stated limitation, not a hidden default.
  * C1 heater TBD (A9.1 SEQ-heater): a TBD c1_heater load may carry a conservative booked power (``booked_W`` with
    evidence class and source); the ledger then counts it ON at that booked power (never OFF). A TBD heater without a
    booked power keeps the ledger incomplete, so no PASS can come from assuming a TBD heater is off.
  * ICP gas (A9.1 HIQ-06 / OQ-A902-05): the primary ICP gas mode is G-REUSE (Hall exhaust / residual propellant, no
    dedicated feed), so ``flow_control_icp_feed`` is installed only in a declared G-ATM / G-XE contingency variant.
  * Status taxonomy: ``PARTIAL_BOUNDARY`` whenever the compressor LOAD is TBD (row 22: the compressor ICD has not
    supplied it; takes precedence); ``INCOMPLETE_EVIDENCE`` for any other TBD, including a known compressor load whose
    supply efficiency is TBD (the boundary is then defined, only its evidence is missing); ``COMPLETE`` otherwise.
Allocations used by the checks (1350 W design allocation row 109; 300 W common allocation incl. the 50 W
controls/thermal allowance row 114, composition accepted in A9.1 OQ-A902-02) are OWNER ALLOCATIONS, never predictions
and never gates. The ICP has no fixed sub-allocation: at every registered condition
P_ICP,available = 1350 - P_common - P_Hall - P_other,active (A9.1 OQ-A902-03, ``icp_power_allocation_check``); the
laboratory 0-500 W RF source is a test capability, not a flight allowance.
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

POWER_BASES = ("steady_state", "step_average", "peak_sampled", "p_bus_1ms_max")
GATE_WINDOW_S = 1.0e-3                # A9.1 OQ-A902-01: 1 ms moving-average window of the gate quantity
GATE_MIN_BANDWIDTH_HZ = 20.0e3        # A9.1 OQ-A902-01: effective measurement bandwidth >= 20 kHz
GATE_MIN_SAMPLE_RATE_SA_S = 100.0e3   # A9.1 OQ-A902-01: >= 100 kSa/s per relevant channel
DIAGNOSTIC_WINDOWS_S = (0.1, 1.0)     # A9.1 OQ-A902-01: 100 ms and 1 s averages, diagnostic/energy metrics only
PASS_BASES = ("p_bus_1ms_max",)      # + a conformant gate_measurement record (A9.1 OQ-A902-01 requirements)
FAIL_BASES = ("p_bus_1ms_max", "step_average", "steady_state")   # averages: duration a multiple of / >> 1 ms
FAIL_BASIS_ASSUMPTION = ("step_average / steady_state bound P_bus,1ms,max from below only when the averaging duration "
                         "is a whole multiple of 1 ms (exact) or much longer than 1 ms (approximate); an unstated "
                         "basis gives NOT_EVALUABLE. A ledger is a SUM of per-slot values: on the p_bus_1ms_max basis "
                         "that sum is a rigorous bound for FAIL only when the slot values are simultaneous (taken in "
                         "the same 1 ms window, e.g. one system-level bus channel split by slot); a sum of per-slot "
                         "1 ms maxima taken at different times is an UPPER bound (conservative for PASS) but not a "
                         "lower bound, so a FAIL on it must be confirmed by the system-level (bus-channel) 1 ms "
                         "maximum (P1MS_SUM_RULE)")
P1MS_SUM_RULE = ("p_bus_1ms_max ledger: FAIL requires slot values from one common 1 ms window (system-level bus-channel "
                 "maximum); summed non-simultaneous per-slot maxima support PASS (upper bound) but a FAIL on them is "
                 "only an indication until the system-level 1 ms maximum confirms it")
PEAK_SAMPLED_RULE = ("an unaveraged sampled peak is a protection-analysis record, not the 1.5 kW gate (A9.1 "
                     "OQ-A902-01): NOT_EVALUABLE in both directions; whether a conformant sampled peak below 1500 W "
                     "may bound P_bus,1ms,max is the OPEN owner question OQ-A910-03 (not implemented before the "
                     "owner rules)")
GATE_MEASUREMENT_KEYS = ("sample_rate_Sa_s", "bandwidth_Hz", "anti_alias_documented", "synchronized", "source")
TRANSIENT_WINDOW = {
    "status": "FROZEN_A9_ENGINEERING_DEFINITION",
    "decision": "A9.1 OQ-A902-01 (docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json)",
    "quantity": "P_bus,1ms,max = max_t (1/1 ms) integral_t^{t+1 ms} P_bus(tau) dtau",
    "requirement": "P_bus,1ms,max < 1500 W for start-up as well as steady state, unless the official RFP later "
                   "explicitly provides a different transient exception",
    "window_s": GATE_WINDOW_S,
    "measurement": ["spacecraft-DC propulsion boundary", "all required channels synchronized",
                    "effective measurement bandwidth >= 20 kHz",
                    "sample rate >= 100 kSa/s per relevant channel or an equivalent direct spacecraft-bus power "
                    "channel", "anti-alias filtering documented", "no step-average may be substituted for this gate"],
    "min_bandwidth_Hz": GATE_MIN_BANDWIDTH_HZ,
    "min_sample_rate_Sa_s": GATE_MIN_SAMPLE_RATE_SA_S,
    "diagnostics_only": ["unaveraged sampled peak (hardware/current/voltage protection analysis; not the 1.5 kW "
                         "system-power gate)", "100 ms and 1 s averages (diagnostic/energy metrics, not substitutes)"],
    "pass_requires_power_basis": list(PASS_BASES),
    "pass_requires_gate_measurement": {"keys": list(GATE_MEASUREMENT_KEYS),
                                       "rule": "sample_rate_Sa_s >= 100e3, bandwidth_Hz >= 20e3, "
                                               "anti_alias_documented and synchronized True, non-empty source"},
    "fail_bases": list(FAIL_BASES), "fail_basis_assumption": FAIL_BASIS_ASSUMPTION,
    "p1ms_sum_rule": P1MS_SUM_RULE,
    "peak_sampled_rule": PEAK_SAMPLED_RULE,
    "note": "an A9 engineering definition pending authoritative RFP wording; the 1 ms window is not an ECSS "
            "requirement (A9.1 preamble); replaces the interim 'PASS only if peak_sampled' rule (a peak_sampled "
            "ledger no longer PASSes)",
    "item": "A902-03", "owner_question": "OQ-A902-01 (ANSWERED_BY_A9_1)", "freeze_point": "NOW",
}
GATE_DEFINITION = TRANSIENT_WINDOW
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
                      "start-up transient: its bus draw enters the gate as P_bus,1ms,max through the pulse (A9.1 "
                      "OQ-A902-01; the unaveraged peak is a protection record only); the pulse energy (row 89 "
                      "'recorded pulse energy') is a measurement record, not a ledger field: the A9-04 DQ-HI-PBUS "
                      "chain (INS-02, one DC channel per slot) defines no pulse-energy record yet (LOCK-1 item)"},
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
        "group": "variant", "rows": [46], "common_allocation": True,
        "load_plane": "dedicated ICP gas-feed valve/flow-controller driver outputs; installed only in a declared "
                      "G-ATM or G-XE contingency variant (A9.1 HIQ-06, OQ-A902-05: primary G-REUSE has no dedicated "
                      "feed and books 0; the capped test port stays in the ICD)"},
    "compressor": {
        "group": "common", "rows": [22], "common_allocation": True,
        "load_plane": "compressor motor-drive electrical input; TBD gives PARTIAL_BOUNDARY until the ICD supplies it "
                      "(row 22)"},
    "thermal_control": {
        "group": "common", "rows": [114], "common_allocation": True, "controls_thermal": True,
        "load_plane": "propulsion-subsystem heaters / active thermal control terminals in the evaluated step"},
    "housekeeping_controls": {
        "group": "common", "rows": [114], "common_allocation": True, "controls_thermal": True,
        "load_plane": "propulsion controller, PPU control electronics, sensors, telemetry/command interface, AND the "
                      "explicitly booked no-load/quiescent draw of energised-but-idle supplies and of the front end "
                      "(the per-slot P/eta model gives 0 W for a 0 W output)"},
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
    "hall_icp_neutralizer": _HALL + ("icp_rf_source", "icp_matching_network", "icp_collector_bias") + _COMMON
                            + ("reserved_dc_port",),
}
VARIANT_OPTIONS = {
    "hall_c1_reference": ("active_cooling",),
    "hall_icp_neutralizer": ("icp_assist_magnet", "active_cooling", "flow_control_icp_feed"),
}
# A9.1 HIQ-06 / OQ-A902-05: ICP gas modes; only G-ATM / G-XE install the dedicated feed slot.
ICP_GAS_MODES = {
    "G-REUSE": {"primary": True, "variant_slot": None,
                "dedicated_flow": "mdot_ICP,dedicated = 0 (the ICP reuses Hall exhaust / residual propellant)"},
    "G-ATM": {"primary": False, "variant_slot": "flow_control_icp_feed",
              "dedicated_flow": "mdot_atm,total = mdot_Hall + mdot_ICP,dedicated (actual routing)"},
    "G-XE": {"primary": False, "variant_slot": "flow_control_icp_feed",
             "dedicated_flow": "mdot_ICP,Xe booked explicitly in the Xe ledger under PHASE_TOTAL_FLOW"},
}
# A9.1 OQ-A902-04: no combined flight C1 + ICP installation in the primary A9 architecture (a new variant would need
# its own mass, power, Xe, reliability, thermal and failure-tree closure); no such variant is declared here.
COMBINED_C1_ICP_FLIGHT_VARIANT = None
PEAK_EVENTS = {  # start-up peak-class events and their slots (row 112; A9.1 SEQ-peaks: at most one rises per step)
    "compressor_spinup": "compressor",
    "c1_heater_preheat": "c1_heater",
    "c1_keeper_ignition": "c1_keeper",
    "magnet_ramp": "hall_magnet_inner",
    "icp_rf_ignition": "icp_rf_source",
    "icp_collector_bias_on": "icp_collector_bias",
    "hall_discharge_ignition": "hall_discharge",
    "active_cooling_start": "active_cooling",
}
# A9.1 SEQ-peaks limits the peak-class loads COMMANDED to rise per step. A load that rises only as the physical
# consequence of the step's declared commanded event is a DEPENDENT rise, not a commanded one (A9-10 review repair):
# in hall_icp_neutralizer the whole Hall discharge current closes through the ICP collector (ICD ICP-22 / ICP-45), so
# at the Hall-ignition step the collector-bias load V_bias x I_collector rises with I_d without a new command. Such a
# rise is excluded from the one-rise count ONLY at a step whose declared event is the key below, is listed in the
# result ('dependent_rises') and still counts in every power ledger and in the 1500 W gate. The C1 reference has no
# peak-class slot coupled this way (its discharge current returns through the cathode common tie, not a peak slot).
DEPENDENT_RISE_RULE = ("A9.1 SEQ-peaks counts loads COMMANDED to rise; a peak-class load whose rise is the physical "
                       "consequence of the step's declared event (icp_collector_bias at hall_discharge_ignition: the "
                       "Hall discharge current closes through the collector, ICD ICP-22 / ICP-45) is a dependent rise, "
                       "reported and kept in the power gate but not counted as a second commanded peak")
DEPENDENT_RISES = {"hall_discharge_ignition": ("icp_collector_bias",)}
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
        {"step_id": "I-S3", "name": "ICP RF ignition on the Hall-feed gas (G-REUSE, no dedicated feed, A9.1 HIQ-06; "
                                   "no thermionic heater)", "event": "icp_rf_ignition",
         "on": ["icp_matching_network", "icp_rf_source"]},
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


def _keys(rec: Mapping, allowed: set, what: str) -> None:
    extra = sorted(str(k) for k in rec if k not in allowed)
    if extra:
        raise BoundaryA9Error(f"{what}: unexpected key(s) {extra}; allowed {sorted(allowed)} (schema parity)")


def _load_record(slot: str, rec) -> dict:
    what = f"load of {slot!r}"
    if not isinstance(rec, Mapping):
        raise BoundaryA9Error(f"{what} must be a record {{'P_W', 'evidence_class', 'source'}} or "
                              f"{{'P_W': 'TBD', 'tbd_requires'}}, got {type(rec).__name__}")
    if "P_W" not in rec:
        raise BoundaryA9Error(f"{what}: 'P_W' missing (no default)")
    plane_key = {"plane"} if slot == "icp_rf_source" else set()
    if slot == "icp_rf_source":
        plane = rec.get("plane")
        if plane != "generator_dc_input":
            raise BoundaryA9Error(f"{what}: plane must be 'generator_dc_input' (got {plane!r}); only the RF generator "
                                  f"DC input crosses the bus boundary, forward/reflected/delivered RF power are "
                                  f"measurement quantities (row 72)")
    elif "plane" in rec:
        raise BoundaryA9Error(f"{what}: 'plane' is defined only for icp_rf_source")
    p = rec["P_W"]
    if isinstance(p, str):
        if p != TBD:
            raise BoundaryA9Error(f"{what}: string value must be exactly {TBD!r}, got {p!r}")
        if "booked_W" in rec:
            # A9.1 SEQ-heater: a TBD C1 heater is ON at its conservative / worst-case booked power (never OFF)
            if slot != "c1_heater":
                raise BoundaryA9Error(f"{what}: 'booked_W' is defined only for c1_heater (A9.1 SEQ-heater)")
            _keys(rec, {"P_W", "tbd_requires", "booked_W", "evidence_class", "source"}, what)
            b = _real(rec["booked_W"], f"{what} booked_W")
            if b <= 0.0:
                raise BoundaryA9Error(f"{what}: booked_W must be > 0 W (a TBD heater is ON, A9.1 SEQ-heater)")
            ec = rec.get("evidence_class")
            if ec not in EVIDENCE_CLASSES:
                raise BoundaryA9Error(f"{what}: evidence_class must be one of {list(EVIDENCE_CLASSES)}, got {ec!r}")
            return {"P_W": b, "tbd_requires": _nonempty(rec, "tbd_requires", what), "evidence_class": ec,
                    "source": _nonempty(rec, "source", what), "booked": True}
        _keys(rec, {"P_W", "tbd_requires"} | plane_key, what)
        return {"P_W": None, "tbd_requires": _nonempty(rec, "tbd_requires", what), "evidence_class": None,
                "source": None}
    _keys(rec, {"P_W", "evidence_class", "source"} | plane_key, what)
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
        _keys(rec, {"value", "tbd_requires"} | ({"path"} if need_path else set()), what)
        return {"value": None, "path": path, "tbd_requires": _nonempty(rec, "tbd_requires", what),
                "evidence_class": None, "source": None}
    _keys(rec, {"value", "evidence_class", "source"} | ({"path"} if need_path else set()), what)
    x = _real(v, what)
    if not (0.0 < x <= 1.0):
        raise BoundaryA9Error(f"{what} must be in (0, 1], got {x!r}")
    ec = rec.get("evidence_class")
    if ec not in EVIDENCE_CLASSES:
        raise BoundaryA9Error(f"{what}: evidence_class must be one of {list(EVIDENCE_CLASSES)}, got {ec!r}")
    return {"value": x, "path": path, "tbd_requires": None, "evidence_class": ec,
            "source": _nonempty(rec, "source", what)}


def _not_installed_ok(slot: str, loads: Mapping, effs: Mapping, config: str) -> None:
    """A not-installed slot is omitted, or passed as a full schema-valid record with exactly 0 W / efficiency 1."""
    if slot in loads:
        rec = loads[slot]
        p = rec.get("P_W") if isinstance(rec, Mapping) else rec
        if isinstance(p, bool) or not isinstance(p, Real) or float(p) != 0.0:
            raise BoundaryA9Error(f"slot {slot!r} is not installed in {config!r} with this variant; it may only be "
                                  f"omitted or passed as exactly 0 W (got {p!r}) - no hidden consumption")
        _load_record(slot, rec)          # same record shape as the schema (evidence_class + source required)
    if slot in effs:
        rec = effs[slot]
        v = rec.get("value") if isinstance(rec, Mapping) else rec
        if isinstance(v, bool) or not isinstance(v, Real) or float(v) != 1.0:
            raise BoundaryA9Error(f"slot {slot!r} is not installed in {config!r}; its efficiency may only be omitted "
                                  f"or exactly 1 (got {v!r})")
        _eff_record(f"efficiency of {slot!r}", rec)


# ------------------------------------------------------------------------------------------------------ ledger
def _gate_measurement(rec):
    """Validate an optional gate-measurement conformance record (A9.1 OQ-A902-01); return (record, conformant)."""
    if rec is None:
        return None, False
    if not isinstance(rec, Mapping):
        raise BoundaryA9Error("gate_measurement must be a mapping")
    _keys(rec, set(GATE_MEASUREMENT_KEYS), "gate_measurement")
    missing = [k for k in GATE_MEASUREMENT_KEYS if k not in rec]
    if missing:
        raise BoundaryA9Error(f"gate_measurement lacks {missing} (no default)")
    fs = _real(rec["sample_rate_Sa_s"], "gate_measurement.sample_rate_Sa_s")
    bw = _real(rec["bandwidth_Hz"], "gate_measurement.bandwidth_Hz")
    for k in ("anti_alias_documented", "synchronized"):
        if not isinstance(rec[k], bool):
            raise BoundaryA9Error(f"gate_measurement.{k} must be a bool")
    src = _nonempty(rec, "source", "gate_measurement")
    out = {"sample_rate_Sa_s": fs, "bandwidth_Hz": bw, "anti_alias_documented": rec["anti_alias_documented"],
           "synchronized": rec["synchronized"], "source": src}
    ok = (fs >= GATE_MIN_SAMPLE_RATE_SA_S and bw >= GATE_MIN_BANDWIDTH_HZ and rec["anti_alias_documented"] is True
          and rec["synchronized"] is True)
    return out, ok


def ledger(config: str, loads: Mapping, efficiencies: Mapping, front_end: Mapping, variant: Sequence = (),
           label: str = "", power_basis=None, gate_measurement=None) -> dict:
    """Spacecraft-side DC bus-power ledger of one configuration in one evaluated step.

    ``loads``/``efficiencies`` must contain every installed slot (``installed_slots(config, variant)``); slots that
    are not installed may be omitted or passed as exactly 0 W / efficiency 1 and are reported as ``NOT_INSTALLED``
    with exactly 0.0 W. ``front_end``: {'value', 'evidence_class', 'source'} or {'value': 'TBD', 'tbd_requires'}.

    Status: ``COMPLETE`` (P_bus known), ``PARTIAL_BOUNDARY`` (compressor draw TBD, row 22) or
    ``INCOMPLETE_EVIDENCE`` (another load or an efficiency TBD). When not complete, ``P_bus_W`` is None and
    ``P_bus_lower_bound_W`` is the rigorous lower bound (TBD loads count 0 W; a TBD efficiency counts 1).
    ``power_basis``: what the step values represent (one of ``POWER_BASES``) or None = unstated; a ledger whose basis
    is not in ``PASS_BASES`` cannot PASS the gate (``rfp_power_gate``, A9.1 OQ-A902-01).
    ``gate_measurement``: optional conformance record of the measurement behind the step values
    ({'sample_rate_Sa_s', 'bandwidth_Hz', 'anti_alias_documented', 'synchronized', 'source'}); malformed records
    raise; the ledger reports whether it meets the A9.1 OQ-A902-01 requirements (``gate_measurement_conformant``).
    A TBD ``c1_heater`` carrying ``booked_W`` is counted ON at that conservative booked power (A9.1 SEQ-heater) and
    listed in ``booked_tbd_slots``; its actual power stays TBD.
    """
    if power_basis is not None and power_basis not in POWER_BASES:
        raise BoundaryA9Error(f"power_basis must be one of {list(POWER_BASES)} or None, got {power_basis!r}")
    gm, gm_ok = _gate_measurement(gate_measurement)
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
        if L.get("booked") and state == "ON":
            state = "ON_BOOKED_TBD"      # A9.1 SEQ-heater: counted ON at the conservative booked power
        items.append({"slot": slot, "group": SLOTS[slot]["group"], "state": state, "P_W": L["P_W"],
                      "efficiency": E["value"], "path": E["path"], "P_bus_W": p_bus,
                      "P_loss_W": None if p_bus is None else p_bus - L["P_W"], "lower_bound_W": lb,
                      "evidence_class": L["evidence_class"], "source": L["source"],
                      "efficiency_evidence_class": E["evidence_class"], "efficiency_source": E["source"],
                      "booked_conservative": bool(L.get("booked")),
                      "booked_tbd_requires": L["tbd_requires"] if L.get("booked") else None})

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
            "label": label, "power_basis": power_basis, "gate_measurement": gm,
            "gate_measurement_conformant": gm_ok, "status": status, "P_bus_W": p_total, "P_bus_lower_bound_W": lower,
            "residual_W": residual, "tbd": tbd, "load_evidence_classes": classes,
            "booked_tbd_slots": [it["slot"] for it in items if it.get("booked_conservative")],
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
    """RFP gate P_bus,1ms,max < 1500 W applied to the steady ledger AND every start-up step (row 108; A9.1 OQ-A902-01).

    PASS only if every ledger is COMPLETE, below the limit, declared ``p_bus_1ms_max`` (``PASS_BASES``) AND carries a
    conformant ``gate_measurement`` record (>= 100 kSa/s, >= 20 kHz, anti-alias documented, synchronized); no step
    average is substituted for the gate. FAIL if a known total or a lower bound reaches the limit on a basis in
    ``FAIL_BASES`` (``FAIL_BASIS_ASSUMPTION``; on ``p_bus_1ms_max`` the ledger sum is a lower bound only for
    simultaneous slot values, so such a FAIL carries ``P1MS_SUM_RULE``: confirm it on the system-level bus-channel
    1 ms maximum, not on summed per-slot maxima). An unaveraged ``peak_sampled`` value is a protection-analysis record,
    not the system-power gate: NOT_EVALUABLE either way (``PEAK_SAMPLED_RULE``; OPEN owner question OQ-A910-03). An
    unstated basis gives NOT_EVALUABLE. Otherwise NOT_EVALUABLE. An empty start-up list is
    refused (the gate covers transients). The result carries the frozen gate definition (``GATE_DEFINITION``).
    """
    if isinstance(startup_steps, (str, Mapping)) or not isinstance(startup_steps, Sequence) or not startup_steps:
        raise BoundaryA9Error("rfp_power_gate needs a non-empty sequence of start-up step ledgers (row 108: start-up "
                              "transients stay below 1.5 kW unless the official RFP allows an exception)")
    rows = []
    for role, led in [("steady", steady)] + [("startup", s) for s in startup_steps]:
        if not isinstance(led, Mapping) or led.get("boundary_version") != BOUNDARY_VERSION:
            raise BoundaryA9Error(f"not a {BOUNDARY_VERSION} ledger: {led!r:.80}")
        v = _verdict_below(led["P_bus_W"], led["P_bus_lower_bound_W"], P_BUS_REQUIREMENT_W, True, "PASS", "FAIL")
        basis = led.get("power_basis")
        note = None
        if basis == "peak_sampled" and v in ("PASS", "FAIL"):
            v, note = "NOT_EVALUABLE", PEAK_SAMPLED_RULE
        elif v == "PASS" and basis not in PASS_BASES:
            v, note = "NOT_EVALUABLE", (f"value basis {basis!r} is not P_bus,1ms,max: no step average is "
                                        f"substituted for the gate (A9.1 OQ-A902-01)")
        elif v == "PASS" and not led.get("gate_measurement_conformant"):
            v, note = "NOT_EVALUABLE", ("declared p_bus_1ms_max without a conformant gate_measurement record "
                                        "(>= 100 kSa/s, >= 20 kHz, anti-alias documented, synchronized channels; "
                                        "A9.1 OQ-A902-01)")
        elif v == "FAIL" and basis == "p_bus_1ms_max":
            note = P1MS_SUM_RULE   # the FAIL stands; confirm it on the system-level 1 ms maximum
        elif v == "FAIL" and basis not in FAIL_BASES:
            v, note = "NOT_EVALUABLE", ("unstated power basis: the value is not shown to bound P_bus,1ms,max from "
                                        "below (it could be an unaveraged peak, A9.1 OQ-A902-01)")
        rows.append({"role": role, "label": led["label"], "status": led["status"], "power_basis": basis,
                     "gate_measurement_conformant": bool(led.get("gate_measurement_conformant")),
                     "P_bus_W": led["P_bus_W"], "P_bus_lower_bound_W": led["P_bus_lower_bound_W"], "verdict": v,
                     "note": note, "measured_only": led["measured_only"],
                     "booked_tbd_slots": list(led.get("booked_tbd_slots", []))})
    vs = {r["verdict"] for r in rows}
    overall = "FAIL" if "FAIL" in vs else ("PASS" if vs == {"PASS"} else "NOT_EVALUABLE")
    return {"gate": "RFP P_bus,1ms,max < 1500 W (steady and start-up; A9.1 OQ-A902-01)",
            "limit_W": P_BUS_REQUIREMENT_W, "strict": True,
            "verdict": overall, "evidence_basis": "measured" if all(r["measured_only"] for r in rows)
            else "includes non-measured loads (not a demonstration)",
            "transient_window_frozen": True, "transient_window": dict(TRANSIENT_WINDOW),
            "caveat": "gate definition frozen as an A9 engineering definition pending authoritative RFP wording "
                      "(A9.1 OQ-A902-01); a PASS on non-measured loads is not a demonstration", "rows": rows}


def p_bus_1ms_max(samples_W: Sequence, sample_rate_Sa_s, bandwidth_Hz, anti_alias_documented: bool,
                  synchronized: bool) -> dict:
    """Evaluate the A9.1 gate quantity from a sampled spacecraft-side bus-power record (W per sample).

    Refuses a record that does not meet the frozen measurement requirements (sample rate >= 100 kSa/s, effective
    bandwidth >= 20 kHz, anti-alias filtering documented, synchronized channels) or whose sample rate does not give
    an integer number of samples per 1 ms window, or that is shorter than 1 ms. Returns P_bus,1ms,max (maximum of the
    1 ms moving mean) and, as diagnostics only, the unaveraged sampled peak and the maximum 100 ms / 1 s means (None
    when the record is shorter than that window). Pure arithmetic on the caller's record; no model, no default.
    """
    fs = _real(sample_rate_Sa_s, "sample_rate_Sa_s")
    bw = _real(bandwidth_Hz, "bandwidth_Hz")
    if fs < GATE_MIN_SAMPLE_RATE_SA_S:
        raise BoundaryA9Error(f"sample rate {fs!r} Sa/s < {GATE_MIN_SAMPLE_RATE_SA_S!r} (A9.1 OQ-A902-01)")
    if bw < GATE_MIN_BANDWIDTH_HZ:
        raise BoundaryA9Error(f"effective bandwidth {bw!r} Hz < {GATE_MIN_BANDWIDTH_HZ!r} (A9.1 OQ-A902-01)")
    if anti_alias_documented is not True or synchronized is not True:
        raise BoundaryA9Error("anti-alias filtering must be documented and all channels synchronized (A9.1 OQ-A902-01)")
    if isinstance(samples_W, (str, Mapping)) or not isinstance(samples_W, Sequence):
        raise BoundaryA9Error("samples_W must be a sequence of bus-power samples in W")
    xs = [_real(x, "bus-power sample") for x in samples_W]

    def _n(window_s: float) -> int:
        n = window_s * fs
        k = int(round(n))
        if abs(n - k) > 1e-9 * max(1.0, n):
            raise BoundaryA9Error(f"sample rate {fs!r} Sa/s gives a non-integer number of samples per {window_s} s")
        return k

    def _max_mean(k: int):
        if k < 1 or len(xs) < k:
            return None
        csum = [0.0]
        for x in xs:
            csum.append(csum[-1] + x)
        return max((csum[i + k] - csum[i]) / k for i in range(len(xs) - k + 1))

    n1 = _n(GATE_WINDOW_S)
    if len(xs) < n1:
        raise BoundaryA9Error(f"record shorter than the 1 ms gate window ({len(xs)} < {n1} samples)")
    return {"P_bus_1ms_max_W": _max_mean(n1), "window_samples": n1, "record_duration_s": len(xs) / fs,
            "diagnostics_only": {"unaveraged_sampled_peak_W": max(xs),
                                 "max_mean_100ms_W": _max_mean(_n(DIAGNOSTIC_WINDOWS_S[0])),
                                 "max_mean_1s_W": _max_mean(_n(DIAGNOSTIC_WINDOWS_S[1]))},
            "power_basis": "p_bus_1ms_max", "definition": TRANSIENT_WINDOW["quantity"],
            "gate_measurement": {"sample_rate_Sa_s": fs, "bandwidth_Hz": bw, "anti_alias_documented": True,
                                 "synchronized": True}}


def icp_power_allocation_check(led: dict) -> dict:
    """A9.1 OQ-A902-03: P_ICP,available = 1350 W - P_common - P_Hall - P_other,active at this registered condition.

    Evaluated on a ``hall_icp_neutralizer`` ledger: P_common = installed common-allocation slots, P_Hall = the Hall
    group, P_other,active = every other installed non-ICP slot (variants, reserved port). The ICP group (RF source DC
    input, matching network, collector/bias) must fit inside it (ICP-45 is demonstrated within this residual budget).
    TBD loads make the result NOT_EVALUABLE unless the known lower bounds already exceed the available power.
    Owner-allocation arithmetic only: not a gate, not a prediction; the 0-500 W laboratory RF source is a test
    capability, not a flight allowance.
    """
    if not isinstance(led, Mapping) or led.get("boundary_version") != BOUNDARY_VERSION:
        raise BoundaryA9Error("icp_power_allocation_check needs a bus_power_boundary_a9_v1 ledger")
    if led.get("configuration") != "hall_icp_neutralizer":
        raise BoundaryA9Error("icp_power_allocation_check applies to hall_icp_neutralizer ledgers only")
    parts = {"common": [], "hall": [], "icp": [], "other": []}
    for it in led["items"]:
        if it["state"] == "NOT_INSTALLED":
            continue
        s = it["slot"]
        if SLOTS[s].get("common_allocation"):
            parts["common"].append(it)
        elif SLOTS[s]["group"] == "hall":
            parts["hall"].append(it)
        elif SLOTS[s]["group"] == "icp":
            parts["icp"].append(it)
        else:
            parts["other"].append(it)

    def _sum(its):
        known = all(i["P_bus_W"] is not None for i in its)
        return (math.fsum(i["P_bus_W"] for i in its) if known else None,
                math.fsum(i.get("lower_bound_W", 0.0) for i in its))
    s = {k: _sum(v) for k, v in parts.items()}
    others_known = all(s[k][0] is not None for k in ("common", "hall", "other"))
    avail = (DESIGN_ALLOCATION_W - s["common"][0] - s["hall"][0] - s["other"][0]) if others_known else None
    avail_ub = DESIGN_ALLOCATION_W - s["common"][1] - s["hall"][1] - s["other"][1]
    icp_val, icp_lb = s["icp"]
    if avail is not None and icp_val is not None:
        verdict = "WITHIN_AVAILABLE" if icp_val <= avail else "EXCEEDS_AVAILABLE"
    elif icp_lb > avail_ub:
        verdict = "EXCEEDS_AVAILABLE"
    else:
        verdict = "NOT_EVALUABLE"
    return {"kind": "OWNER_ALLOCATION_CHECK (A9.1 OQ-A902-03; not a gate, not a prediction)",
            "relation": "P_ICP,available = 1350 - P_common - P_Hall - P_other,active",
            "design_allocation_W": DESIGN_ALLOCATION_W,
            "P_common_W": s["common"][0], "P_Hall_W": s["hall"][0], "P_other_active_W": s["other"][0],
            "P_ICP_available_W": avail, "P_ICP_available_upper_bound_W": avail_ub,
            "P_ICP_W": icp_val, "P_ICP_lower_bound_W": icp_lb, "verdict": verdict,
            "label": led.get("label", "")}


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


def _heater_rule(sid: str, h, stable: bool, st: dict, violations: list, not_evaluable: list) -> None:
    """Row 112 (revised SEQ-1): C1 heater reduced/disabled only after keeper and discharge are stable.

    ``st`` carries the heater history: ``last_known`` (last numeric value, kept across TBD steps), ``prev_tbd``
    (previous step TBD) and ``on`` (heater was on, known > 0 or TBD). A TBD heater is treated as ON with unknown
    power (an OFF heater must be passed as exactly 0 W). Without both stability flags: a drop below the last known
    value, or to 0 W after a TBD step, is a violation; a change that cannot be classified is NOT_EVALUABLE.
    """
    rule = "C1 heater reduced/disabled only after keeper and discharge are stable per cathode procedure (row 112)"
    if not stable and st["on"]:
        if h is None:
            if not st["prev_tbd"] and st["last_known"]:
                not_evaluable.append({"step_id": sid, "rule": rule, "detail": {
                    "from_W": st["last_known"], "to_W": TBD, "why": "heater power TBD: a reduction cannot be excluded"}})
        elif st["last_known"] is not None and h < st["last_known"]:
            violations.append({"step_id": sid, "rule": rule, "detail": {"from_W": st["last_known"], "to_W": h,
                                                                        "via_tbd": st["prev_tbd"]}})
        elif st["prev_tbd"] and h == 0.0:
            violations.append({"step_id": sid, "rule": rule, "detail": {"from_W": TBD, "to_W": h, "via_tbd": True}})
        elif st["prev_tbd"]:
            not_evaluable.append({"step_id": sid, "rule": rule, "detail": {
                "from_W": TBD, "to_W": h, "why": "previous heater power TBD: a reduction cannot be excluded"}})
    if h is None:
        st["on"], st["prev_tbd"] = True, True
    else:
        st["on"] = st["on"] or h > 0.0
        st["prev_tbd"] = False
        st["last_known"] = h


def _peak_rises(prev: dict, cur: dict, peak_slots: tuple) -> tuple:
    """Peak-class slots whose load certainly rises (known increase, or exactly 0 W -> TBD) and those that may rise
    (any other transition involving TBD, except TBD -> exactly 0 W)."""
    sure, maybe = [], []
    for s in peak_slots:
        a, b = prev[s], cur[s]
        if a is not None and b is not None:
            if b > a:
                sure.append(s)
        elif b is None and a == 0.0:
            sure.append(s)
        elif b is None or b > 0.0:
            maybe.append(s)
    return sure, maybe


def check_startup_sequence(config: str, steps: Sequence, front_end: Mapping, variant: Sequence = ()) -> dict:
    """Evaluate a time-ordered start-up sequence (revised SEQ-1, row 112) and the transient RFP gate (row 108).

    ``steps``: list of {'step_id', 'event' (a PEAK_EVENTS key or None), 'loads', 'efficiencies', optional 'flags'
    {'keeper_stable', 'discharge_stable'}, optional 'power_basis' (``POWER_BASES``), optional 'gate_measurement'
    (conformance record, see ``ledger``), optional 'phase' ('steady'
    only on the last step)}. The last step must be the steady step. Rule violations (simultaneous peaks by declared
    event AND by actual load increase, forbidden heater reduction, enforced order) are reported, not raised; rules
    that cannot be evaluated because of TBD loads are reported as ``not_evaluable``; malformed input raises.
    ``sequence_status``: SEQUENCE_RULE_VIOLATION > RULES_NOT_EVALUABLE > RULES_SATISFIED.
    """
    inst = installed_slots(config, variant)
    if isinstance(steps, (str, Mapping)) or not isinstance(steps, Sequence) or len(steps) < 2:
        raise BoundaryA9Error("a start-up sequence needs at least one start-up step and a final steady step")
    peak_slots = tuple(s for s in ALL_SLOTS if s in set(PEAK_EVENTS.values()) and s in inst)
    ledgers, violations, not_evaluable, seen_events, ids = [], [], [], {}, set()
    dependent_rises = []
    heater = {"last_known": None, "prev_tbd": False, "on": False}
    prev_p = None
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
            violations.append({"step_id": sid, "rule": "one peak-class event per step (row 112; A9.1 SEQ-peaks)",
                               "detail": events})
        led = ledger(config, st.get("loads"), st.get("efficiencies"), front_end, variant, label=sid,
                     power_basis=st.get("power_basis"), gate_measurement=st.get("gate_measurement"))
        ledgers.append(led)
        # a booked TBD heater (A9.1 SEQ-heater) is ON at a conservative booking; its actual power stays TBD here
        cur_p = {it["slot"]: (None if it.get("booked_conservative") else it["P_W"]) for it in led["items"]}
        if prev_p is not None:
            sure, maybe = _peak_rises(prev_p, cur_p, peak_slots)
            dep_ok = {d for e in events for d in DEPENDENT_RISES.get(e, ())}
            dep = [x for x in sure + maybe if x in dep_ok]
            if dep:
                dependent_rises.append({"step_id": sid, "events": events, "dependent_slots": dep,
                                        "rule": DEPENDENT_RISE_RULE})
            sure = [x for x in sure if x not in dep_ok]
            maybe = [x for x in maybe if x not in dep_ok]
            rule = ("at most one peak-class slot load commanded to rise per step (row 112; A9.1 SEQ-peaks baseline "
                    "rule; checked by load, independent of event labels, except a declared dependent rise "
                    "(DEPENDENT_RISES) of the step's own event)")
            if len(sure) > 1:
                violations.append({"step_id": sid, "rule": rule, "detail": sure})
            elif len(sure) + len(maybe) > 1:
                not_evaluable.append({"step_id": sid, "rule": rule,
                                      "detail": {"rising": sure, "TBD_may_rise": maybe}})
        prev_p = cur_p
        if "c1_heater" in inst:
            flags = st.get("flags") or {}
            stable = flags.get("keeper_stable") is True and flags.get("discharge_stable") is True
            _heater_rule(sid, cur_p["c1_heater"], stable, heater, violations, not_evaluable)
    for a, b in ENFORCED_ORDER[config]:
        if a in seen_events and b in seen_events and not seen_events[a] < seen_events[b]:
            violations.append({"step_id": steps[seen_events[b]]["step_id"], "rule": f"{a} before {b}",
                               "detail": {a: seen_events[a], b: seen_events[b]}})
        if b in seen_events and a not in seen_events:
            violations.append({"step_id": steps[seen_events[b]]["step_id"], "rule": f"{a} before {b}",
                               "detail": f"{a} missing"})
    gate = rfp_power_gate(ledgers[-1], ledgers[:-1])
    status = ("SEQUENCE_RULE_VIOLATION" if violations else
              ("RULES_NOT_EVALUABLE" if not_evaluable else "RULES_SATISFIED"))
    return {"boundary_version": BOUNDARY_VERSION, "configuration": config, "variant": list(variant),
            "sequence_status": status, "violations": violations, "not_evaluable": not_evaluable,
            "dependent_rises": dependent_rises, "transient_gate": gate,
            "steady_allocation_checks": allocation_checks(ledgers[-1]),
            "steady_icp_power_allocation": (icp_power_allocation_check(ledgers[-1])
                                            if config == "hall_icp_neutralizer" else None),
            "steps": [{"step_id": led["label"], "status": led["status"], "power_basis": led["power_basis"],
                       "P_bus_W": led["P_bus_W"], "P_bus_lower_bound_W": led["P_bus_lower_bound_W"]}
                      for led in ledgers]}
