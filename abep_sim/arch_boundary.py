"""Common bus-power boundary for Hall-only / RF+Hall / ECR+Hall  (bus_power_boundary_v1).

ONE electrical boundary -- the spacecraft DC bus input to the propulsion subsystem -- applied identically to the three
Hall-accelerated architectures of the RFP chain (atmospheric path: intake -> filter -> compressor -> gas chamber ->
valve; Xe path: Xe chamber -> valve; both feed ionization/discharge -> acceleration/thrust). Every architecture carries
the same eight common components; the pre-ionized architectures add exactly their pre-ionizer components. An
architecture compared on this boundary can never be selected on discharge-only power.

Pure module: standard library only, no physics, no I/O, not wired into ``archengine`` (wiring it would be a model
change, see docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md). **No default loads or efficiencies
exist anywhere in this module**: every component of the architecture needs an explicit delivered load and an explicit
bus-to-load efficiency (a permanent-magnet ``ecr_magnet`` is passed as 0 W with efficiency 1). Evidence for
efficiencies is documented in BUS_POWER_BOUNDARY.md as data for callers, never as defaults here.

Conventions (per component, see ``COMPONENT_DEFINITIONS`` and the boundary document):
  * ``P_load_W``  power delivered at the component's load-side reference plane (time-averaged, steady operating mode).
  * ``efficiency`` end-to-end ratio P_load / P_bus from the bus input terminal to that reference plane at the actual
    operating point (converter, generator, filter, harness, matching network, isolator, fixed overheads).
  * ``P_bus_W = P_load_W / efficiency`` and ``P_loss_W = P_bus_W - P_load_W`` per component.
  * Ledger ``P_bus_W`` is the destination-side total (delivered + converted-to-heat); ``residual_W`` is it minus the
    source-side total (sum of the per-component bus draws). Conservation is a gate (CLAUDE.md rule 4): a residual above
    a rounding-level tolerance raises instead of returning a ledger.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real

BOUNDARY_VERSION = "bus_power_boundary_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")

COMMON_COMPONENTS = (
    "hall_discharge",    # anode-cathode discharge supply output
    "hall_magnet",       # Hall magnetic-circuit coil supply output (0 W / efficiency 1 for permanent magnets)
    "cathode_keeper",    # cathode sustaining (keeper) supply output
    "cathode_heater",    # cathode heater supply output in the evaluated mode (0 W / efficiency 1 if off or heaterless)
    "flow_control",      # air- and Xe-path valves / flow controllers (all propellant-feed actuators)
    "compressor",        # compressor motor-drive electrical input (motor + drive losses are inside the load)
    "thermal_control",   # propulsion-subsystem heaters and active thermal control drawn from the bus
    "housekeeping",      # propulsion controller, PPU digital control, sensors, telemetry interface
)
PREIONIZER_COMPONENTS = {
    "hall_only": (),
    "rf_hall": ("rf_source",),                      # net RF power into the coil/antenna feed terminals
    "ecr_hall": ("ecr_source", "ecr_magnet"),       # net microwave power into the coupling structure; resonance-field supply
}
REQUIRED_COMPONENTS = {arch: COMMON_COMPONENTS + PREIONIZER_COMPONENTS[arch] for arch in ARCHITECTURES}
ALL_COMPONENTS = COMMON_COMPONENTS + ("rf_source", "ecr_source", "ecr_magnet")

COMPONENT_DEFINITIONS = {
    "hall_discharge": "load plane: anode-cathode terminals at the thruster (V_d x I_d, time-averaged). Efficiency chain: "
                      "bus input filter -> discharge converter -> output filter -> harness. Series-connected coil drops "
                      "are booked under hall_magnet, not here.",
    "hall_magnet": "load plane: Hall electromagnet coil terminals (I^2 R). Efficiency chain: bus -> magnet supply -> harness. "
                   "Permanent-magnet circuit: 0 W with efficiency 1, passed explicitly.",
    "cathode_keeper": "load plane: cathode keeper (sustaining-discharge) terminals. For a heaterless or plasma-bridge "
                      "neutralizer, its sustaining supply output; any RF/microwave generator of such a cathode is inside "
                      "the efficiency.",
    "cathode_heater": "load plane: cathode heater terminals in the evaluated mode. 0 W with efficiency 1 when the heater is "
                      "off in that mode or the cathode is heaterless, passed explicitly.",
    "flow_control": "load plane: terminals of every propellant-feed actuator on the atmospheric path (valve after the gas "
                    "chamber) and the Xe path (valve after the Xe chamber): proportional/latch valves, thermothrottles, "
                    "mass-flow-controller electronics.",
    "compressor": "load plane: electrical input of the compressor motor drive (motor, bearings and drive losses are part "
                  "of the load, as abep_sim.compressor P_el). Efficiency chain: bus -> motor-bus converter -> harness.",
    "thermal_control": "load plane: terminals of propulsion-subsystem heaters and active thermal hardware powered from the "
                       "bus in the evaluated mode (Xe tank/line/valve heaters, gas-chamber heaters, PPU heaters). Passive "
                       "radiators draw nothing.",
    "housekeeping": "load plane: propulsion controller / PPU control electronics, sensors (pressure, temperature, current) "
                    "and the telemetry/command interface. Spacecraft-level housekeeping is outside the boundary.",
    "rf_source": "load plane: net RF power (forward minus reflected) at the RF pre-ionizer coil/antenna feed terminals. "
                 "Efficiency chain: bus -> DC supply -> RF generator (incl. drive/auxiliary draw) -> matching network -> "
                 "RF cable. Coil ohmic loss and plasma coupling are part of the load (ionization block physics).",
    "ecr_source": "load plane: net microwave power at the ECR coupling structure input (waveguide/antenna). Efficiency "
                  "chain: bus -> HV/DC supply -> magnetron or solid-state amplifier (incl. filament/driver/bias) -> "
                  "isolator/circulator -> feed line. Absorption in the plasma is part of the load.",
    "ecr_magnet": "load plane: ECR resonance-field coil terminals. Permanent-magnet ECR circuit: 0 W with efficiency 1, "
                  "passed explicitly.",
}

# rounding-level tolerance of the conservation gate (relative to the source-side total, with a 1 W floor)
_CONSERVATION_REL_TOL = 1e-12
_FROZEN = {arch: tuple(REQUIRED_COMPONENTS[arch]) for arch in ARCHITECTURES}


def _real(value, what: str) -> float:
    """A finite real number (bool refused); -0.0 is normalised to 0.0."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{what} must be a real number, got {type(value).__name__} {value!r}")
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"{what} must be finite, got {x!r}")
    return x + 0.0


def _check_keys(name: str, given: Mapping, required: tuple, arch: str) -> None:
    keys = set(given.keys())
    missing = [c for c in required if c not in keys]
    extra = sorted(str(k) for k in keys if k not in required)
    if missing or extra:
        raise ValueError(f"{name} for {arch!r} must have exactly the components {list(required)} "
                         f"(boundary {BOUNDARY_VERSION}); missing {missing}, extra {extra}")


def bus_power_ledger(arch: str, loads: dict, efficiencies: dict) -> dict:
    """Bus-power ledger of one architecture operating point on the common boundary.

    ``loads``: component -> delivered load-side power [W] (finite, >= 0). ``efficiencies``: component -> DC-bus-to-load
    efficiency in (0, 1]. Both must contain exactly ``REQUIRED_COMPONENTS[arch]`` (no missing, no extra keys; nothing
    is defaulted). Returns ``{'boundary_version', 'architecture', 'P_bus_W', 'items', 'residual_W'}`` with one item
    ``{'component', 'P_load_W', 'efficiency', 'P_bus_W', 'P_loss_W'}`` per required component, in the order of
    ``REQUIRED_COMPONENTS[arch]``.

    Raises ValueError for an unknown architecture, a non-mapping input, a missing or extra component (in either
    mapping), a missing efficiency, an efficiency outside (0, 1], a negative or non-finite load, any non-real or bool
    value, or a bus draw that overflows. Raises RuntimeError if the public boundary definition was modified at runtime
    or if the conservation gate fails.
    """
    if not isinstance(arch, str) or arch not in _FROZEN:
        raise ValueError(f"unknown architecture {arch!r}; {BOUNDARY_VERSION} defines {list(ARCHITECTURES)}")
    required = _FROZEN[arch]
    if tuple(REQUIRED_COMPONENTS.get(arch, ())) != required:
        raise RuntimeError(f"REQUIRED_COMPONENTS[{arch!r}] was modified at runtime; {BOUNDARY_VERSION} is frozen "
                           f"(a different component set needs a new boundary version)")
    if not isinstance(loads, Mapping):
        raise ValueError(f"loads must be a mapping component -> W, got {type(loads).__name__}")
    if not isinstance(efficiencies, Mapping):
        raise ValueError(f"efficiencies must be a mapping component -> efficiency, got {type(efficiencies).__name__}")
    _check_keys("loads", loads, required, arch)
    _check_keys("efficiencies", efficiencies, required, arch)

    items = []
    for comp in required:
        p_load = _real(loads[comp], f"load of {comp!r}")
        if p_load < 0.0:
            raise ValueError(f"load of {comp!r} must be >= 0 W, got {p_load!r}")
        eta = _real(efficiencies[comp], f"efficiency of {comp!r}")
        if not (0.0 < eta <= 1.0):
            raise ValueError(f"efficiency of {comp!r} must be in (0, 1], got {eta!r}")
        p_bus = p_load / eta
        if not math.isfinite(p_bus):
            raise ValueError(f"bus draw of {comp!r} overflows ({p_load!r} W / {eta!r})")
        items.append({"component": comp, "P_load_W": p_load, "efficiency": eta,
                      "P_bus_W": p_bus, "P_loss_W": p_bus - p_load})

    try:
        source_total = math.fsum(it["P_bus_W"] for it in items)
        destination_total = math.fsum(it["P_load_W"] for it in items) + math.fsum(it["P_loss_W"] for it in items)
    except OverflowError as exc:
        raise ValueError(f"total bus draw overflows ({exc})") from None
    if not (math.isfinite(source_total) and math.isfinite(destination_total)):
        raise ValueError("total bus draw overflows")
    residual = destination_total - source_total
    if abs(residual) > _CONSERVATION_REL_TOL * max(source_total, 1.0):
        raise RuntimeError(f"conservation gate failed: residual {residual!r} W on {source_total!r} W ({BOUNDARY_VERSION})")
    return {"boundary_version": BOUNDARY_VERSION, "architecture": arch, "P_bus_W": destination_total,
            "items": items, "residual_W": residual}
