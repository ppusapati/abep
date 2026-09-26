"""Neutralizer / cathode system integration for the three thrust architectures (CATHINT, lane 19).

Architectures (exact ids): ``hall_only``, ``rf_hall``, ``ecr_hall``. The RF/ECR arms change only the pre-ionization
method; the Hall accelerator, feed state, cathode and bus boundary are common. The cathode is a Xe-fed LaB6 hollow
cathode (RFP context); alternatives appear only as evidence notes in the lane documentation.

What this module does
---------------------
Pure functions with explicit inputs. There are no default physical or efficiency values anywhere in this file: every
number enters as an argument, and the scenario-level entry point takes :class:`Sourced` values that carry a source
and an evidence class (docs/EVIDENCE.md). Missing inputs raise; an input that is genuinely unknown must be passed as
:class:`TBD` (only where the output can report the gap instead of a number). Nothing here is wired into
``archengine`` (wiring would be a model change; goldens must not move).

Relations (sources and evidence classes are recorded in
``docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json``):

* current continuity (Kirchhoff) for a floating spacecraft with a current-free plume:
  ``I_emit = I_d + I_keeper + I_interstage``; the beam-neutralizing current is *part of* ``I_d`` (Goebel & Katz 2008,
  Eqs. 7.2-24 to 7.2-26), so a Hall cathode never needs ``I_d + I_beam``;
* a Hall-closure-free envelope for ``I_d``: an upper bound from the power available to the discharge supply and a
  lower bound from momentum/energy conservation, ``T <= sqrt(2 mdot P_jet)`` (Cauchy-Schwarz over the exhaust);
* Richardson-Dushman emission with an optional linear work-function temperature term (Goebel & Katz Eqs. 6.3-1..3);
* the Lafferty LaB6 evaporation fit ``W = 10**(C - B/T) / sqrt(T)`` (as given in Goebel et al. IEPC-2017-276, Eq. 2)
  and a constant-temperature, constant-area insert-life estimate;
* cathode Xe flow laws and the mission Xe mass (firing, starts, standby);
* an O2 poisoning screen against the reported LaB6 evidence (no atomic-O or N2 threshold exists in the accessed
  sources: those return ``NO_QUANTITATIVE_EVIDENCE``);
* the start-up bus-power transient per architecture on the bus-power boundary components.

Absolute Hall performance is NOT produced here. ``I_d`` and ``I_beam`` are inputs whose basis must be declared:
``admitted_closure`` (checked against ``abep_sim.hall_ensemble.require_admitted``; the credible set is empty today, so
this basis is refused), ``hardware_measurement`` (evidence class must be ``measured``) or ``conditional_scenario``
(owner "if" values; results are conditional statements that support milestone A only). Screening candidates are
never a performance source.

Other lanes' artefacts (``abep_sim/arch_boundary.py``, ``docs/evidence/cathode/``) are resolved lazily and never at
import time; a clear error is raised if they are missing.
"""
from __future__ import annotations

import importlib
import json
import math
import os
from dataclasses import dataclass
from typing import Mapping, Sequence

from .constants import E_CHARGE, K_B

CATHODE_INTEGRATION_VERSION = "cathode_integration_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")

# --- bus-power boundary contract (abep_sim/arch_boundary.py, another lane; referenced, never imported at load time)
BOUNDARY_VERSION = "bus_power_boundary_v1"
BOUNDARY_MODULE = "abep_sim.arch_boundary"
COMMON_BOUNDARY_COMPONENTS = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control",
                              "compressor", "thermal_control", "housekeeping")
ARCH_EXTRA_BOUNDARY_COMPONENTS = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}
CATHODE_BOUNDARY_COMPONENTS = ("cathode_keeper", "cathode_heater")
PREIONIZER_COMPONENTS = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source",)}

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
OPERATING_POINT_BASES = ("admitted_closure", "hardware_measurement", "conditional_scenario")
INTERSTAGE_TOPOLOGIES = ("floating", "discharge_circuit_referenced", "separately_biased")
KEEPER_MODES = ("off_floating", "on")
FLOW_LAWS = ("fixed_mg_s", "fraction_of_anode_flow")
POISONING_STATUSES = ("WITHIN_REPORTED_NO_DEGRADATION", "IN_REPORTED_DEGRADATION_RANGE", "NO_EVIDENCE_AT_THIS_STATE",
                      "NO_QUANTITATIVE_EVIDENCE", "TBD")

# Numerical bracket for the Richardson-Dushman inversion only (not a physical limit): a solution outside it raises.
T_SEARCH_MIN_K = 300.0
T_SEARCH_MAX_K = 4000.0

SECONDS_PER_HOUR = 3600.0           # exact
MG_PER_KG = 1.0e6                   # exact
TORR_TO_PA = 101325.0 / 760.0       # exact by definition of the torr
CELSIUS_TO_KELVIN = 273.15          # exact

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
DATA_FILE = os.path.join(REPO_ROOT, "docs", "architecture_comparison", "cathode_integration",
                         "cathode_integration_data_v1.json")
CATHODE_DOSSIER_DIR_REL = "docs/evidence/cathode"


class CathodeIntegrationError(ValueError):
    """Refusal: missing, inconsistent or out-of-contract input. Never silently replaced by a default."""


# ------------------------------------------------------------------------------------------------ input carriers

@dataclass(frozen=True)
class Sourced:
    """A number with its unit, source and evidence class (docs/EVIDENCE.md quantity type)."""
    value: float
    unit: str
    source: str
    evidence_class: str

    def __post_init__(self):
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise CathodeIntegrationError(f"Sourced.value must be a number, got {self.value!r}")
        if not math.isfinite(float(self.value)):
            raise CathodeIntegrationError(f"Sourced.value must be finite, got {self.value!r}")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise CathodeIntegrationError("Sourced.unit is required")
        if not isinstance(self.source, str) or not self.source.strip():
            raise CathodeIntegrationError("Sourced.source is required (a citation, data-file id or scenario label)")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise CathodeIntegrationError(f"evidence_class {self.evidence_class!r} not in {EVIDENCE_CLASSES}")


@dataclass(frozen=True)
class TBD:
    """An input that is explicitly unknown. ``requires`` names what would resolve it."""
    requires: str

    def __post_init__(self):
        if not isinstance(self.requires, str) or not self.requires.strip():
            raise CathodeIntegrationError("TBD.requires must say what is needed")


@dataclass(frozen=True)
class DischargeOperatingPoint:
    """Hall discharge-supply current and ion beam current at the operating point (Hall block output)."""
    I_d_A: Sourced
    I_beam_A: Sourced
    basis: str                      # one of OPERATING_POINT_BASES
    closure_member_id: str | None   # required iff basis == "admitted_closure", otherwise None


@dataclass(frozen=True)
class InterstageCircuit:
    """Electrical topology of the pre-ionizer / interstage (rf_hall, ecr_hall only).

    * ``floating``: no DC return path; net steady current zero (Kirchhoff), so no extra cathode demand.
    * ``discharge_circuit_referenced``: electrode tied into the discharge-supply circuit; its current is already
      inside the measured discharge-supply current I_d.
    * ``separately_biased``: electrode on its own supply returning to cathode common; ``I_net_electron_A`` is the net
      electron current it collects (positive = additional emission demand on the cathode).
    """
    topology: str
    I_net_electron_A: Sourced | None
    declared_by: str                # design document / evidence that fixes the topology


@dataclass(frozen=True)
class KeeperState:
    mode: str                       # "off_floating" | "on"
    I_keeper_A: Sourced | None      # required iff mode == "on"
    V_keeper_V: Sourced | None      # required iff mode == "on"


@dataclass(frozen=True)
class CathodeFlowSpec:
    law: str                        # "fixed_mg_s" | "fraction_of_anode_flow"
    value: Sourced                  # mg/s for fixed_mg_s; dimensionless fraction for fraction_of_anode_flow
    anode_mdot_mg_s: Sourced | None  # required iff law == "fraction_of_anode_flow"


@dataclass(frozen=True)
class MissionUsage:
    mission_h: Sourced
    firing_h: Sourced
    required_firing_h: Sourced      # the firing requirement the life margin is referred to
    starts: Sourced
    ignition_flow_mg_s: Sourced     # cathode Xe flow while igniting (before the discharge takes over)
    ignition_duration_s: Sourced    # per start
    standby_flow_mg_s: Sourced      # cathode Xe flow during non-firing hours (0 declared explicitly if off)
    standby_h: Sourced


@dataclass(frozen=True)
class EmitterSpec:
    emitting_area_cm2: Sourced
    richardson_A_A_cm2K2: Sourced
    work_function_eV: Sourced
    work_function_T_coeff_eV_K: Sourced   # 0 for constant-work-function parameter sets
    evaporation_B_K: Sourced
    evaporation_C: Sourced
    insert_density_g_cm3: Sourced
    usable_thickness_cm: Sourced
    redeposition_fraction: Sourced        # 0 = no redeposition (conservative)
    peak_temperature_offset_K: Sourced    # >= 0: evaporation evaluated at T_uniform + offset (axial non-uniformity)


@dataclass(frozen=True)
class StartupPhase:
    name: str
    duration_s: Sourced
    loads_W: Mapping[str, Sourced]        # bus-power boundary component -> load-side power during the phase


@dataclass(frozen=True)
class CurrentEnvelopeInputs:
    thrust_N: Sourced
    mdot_total_kg_s: Sourced          # all mass leaving the thruster (anode + cathode)
    V_d_V: Sourced
    P_other_to_jet_W: Sourced         # every other power that can end up in the jet (pre-ionizer, keeper, inflow enthalpy)
    P_available_for_discharge_W: Sourced


@dataclass(frozen=True)
class PoisoningInputs:
    p_O2_equiv_at_emitter_Torr: Sourced | TBD
    cold_region_temperature_offset_K: Sourced   # >= 0: screen at T_uniform - offset (cooler insert regions poison first)
    other_species_at_emitter: tuple      # names of other oxidizing/reactive species expected at the emitter (e.g. "O", "N2")
    evidence_points: tuple               # O2 evidence points (from the data file, see oxygen_poisoning_screen)


@dataclass(frozen=True)
class CathodeIntegrationInputs:
    operating_point: DischargeOperatingPoint
    interstage: InterstageCircuit | None     # must be None for hall_only, required for rf_hall / ecr_hall
    keeper: KeeperState
    heater_steady_W: Sourced
    flow: CathodeFlowSpec
    mission: MissionUsage
    emitter: EmitterSpec
    startup: Sequence[StartupPhase]
    envelope: CurrentEnvelopeInputs | TBD
    poisoning: PoisoningInputs


# ------------------------------------------------------------------------------------------------ small helpers

def _num(name: str, x, *, lo: float | None = None, hi: float | None = None, lo_open: bool = False) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise CathodeIntegrationError(f"{name} must be a finite number, got {x!r}")
    x = float(x)
    if lo is not None and (x < lo or (lo_open and x == lo)):
        raise CathodeIntegrationError(f"{name} = {x} below its physical range ({'>' if lo_open else '>='} {lo})")
    if hi is not None and x > hi:
        raise CathodeIntegrationError(f"{name} = {x} above its physical range (<= {hi})")
    return x


def _s(name: str, q, unit: str, *, lo: float | None = None, hi: float | None = None, lo_open: bool = False) -> float:
    """Unwrap a Sourced input, checking presence, type and unit."""
    if q is None:
        raise CathodeIntegrationError(f"missing input: {name} ({unit})")
    if isinstance(q, TBD):
        raise CathodeIntegrationError(f"input {name} is TBD ({q.requires}); this relation cannot be evaluated without it")
    if not isinstance(q, Sourced):
        raise CathodeIntegrationError(f"input {name} must be a Sourced value, got {type(q).__name__}")
    if q.unit != unit:
        raise CathodeIntegrationError(f"input {name} has unit {q.unit!r}, expected {unit!r}")
    return _num(name, q.value, lo=lo, hi=hi, lo_open=lo_open)


def _check_arch(arch: str) -> None:
    if arch not in ARCHITECTURES:
        raise CathodeIntegrationError(f"unknown architecture {arch!r}; expected one of {ARCHITECTURES}")


def boundary_components(arch: str) -> tuple:
    """Bus-power boundary components allowed for ``arch`` (bus_power_boundary_v1 naming contract)."""
    _check_arch(arch)
    return COMMON_BOUNDARY_COMPONENTS + ARCH_EXTRA_BOUNDARY_COMPONENTS[arch]


# ------------------------------------------------------------------------------------------------ physics relations

def richardson_current_density_A_cm2(T_K: float, A_A_cm2K2: float, phi0_eV: float, alpha_eV_K: float) -> float:
    """J = A T^2 exp(-e(phi0 + alpha T)/(k T))  [A/cm^2]  (Goebel & Katz 2008, Eqs. 6.3-1..6.3-3)."""
    T = _num("T_K", T_K, lo=0.0, lo_open=True)
    A = _num("A_A_cm2K2", A_A_cm2K2, lo=0.0, lo_open=True)
    phi0 = _num("phi0_eV", phi0_eV, lo=0.0, lo_open=True)
    alpha = _num("alpha_eV_K", alpha_eV_K)
    return A * T * T * math.exp(-E_CHARGE * (phi0 + alpha * T) / (K_B * T))


def emitter_temperature_K(J_A_cm2: float, A_A_cm2K2: float, phi0_eV: float, alpha_eV_K: float, *,
                          T_min_K: float, T_max_K: float) -> float:
    """Temperature at which Richardson-Dushman emission equals ``J`` (bisection; J(T) is monotonic for T > 0).

    The search bracket is an explicit input: a request outside it raises instead of returning an edge value.
    """
    J = _num("J_A_cm2", J_A_cm2, lo=0.0, lo_open=True)
    lo = _num("T_min_K", T_min_K, lo=0.0, lo_open=True)
    hi = _num("T_max_K", T_max_K, lo=lo, lo_open=True)
    f = lambda T: richardson_current_density_A_cm2(T, A_A_cm2K2, phi0_eV, alpha_eV_K)
    if f(lo) > J:
        raise CathodeIntegrationError(f"J = {J} A/cm2 is reached below T_min_K = {lo} K")
    if f(hi) < J:
        raise CathodeIntegrationError(f"J = {J} A/cm2 needs more than T_max_K = {hi} K")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < J:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi)


def lafferty_evaporation_rate_g_cm2_s(T_K: float, B_K: float, C: float) -> float:
    """W = 10**(C - B/T) / sqrt(T)  [g cm^-2 s^-1]  (Lafferty fit as given in Goebel et al. IEPC-2017-276, Eq. 2)."""
    T = _num("T_K", T_K, lo=0.0, lo_open=True)
    B = _num("B_K", B_K, lo=0.0, lo_open=True)
    C = _num("C", C)
    return 10.0 ** (C - B / T) / math.sqrt(T)


def evaporation_limited_life_h(T_evap_K: float, B_K: float, C: float, density_g_cm3: float, usable_thickness_cm: float,
                               redeposition_fraction: float) -> float:
    """Insert life when evaporation removes the usable areal mass at a constant temperature.

    life = rho * w_usable / (W(T) * (1 - f_redep)). Constant area and temperature: conservative with respect to the
    growth of the insert bore (Goebel & Katz 2008 p. 302-303), NOT conservative with respect to axial temperature
    peaking unless ``T_evap_K`` already carries the peak (IEPC-2017-276).
    """
    rho = _num("density_g_cm3", density_g_cm3, lo=0.0, lo_open=True)
    w = _num("usable_thickness_cm", usable_thickness_cm, lo=0.0, lo_open=True)
    f = _num("redeposition_fraction", redeposition_fraction, lo=0.0)
    if f >= 1.0:
        raise CathodeIntegrationError("redeposition_fraction must be < 1 (full redeposition gives no finite life)")
    W = lafferty_evaporation_rate_g_cm2_s(T_evap_K, B_K, C) * (1.0 - f)
    return rho * w / W / SECONDS_PER_HOUR


def electron_current_budget(I_d_A: float, I_beam_A: float, I_keeper_A: float, I_interstage_A: float) -> dict:
    """Cathode emission required by current continuity (floating spacecraft, current-free plume).

    Conventional currents INTO the plasma: anode +I_d, keeper +I_keeper (it collects electrons), interstage electrode
    +I_interstage (net electron collection), cathode -I_emit, plume ions -I_beam and plume electrons +I_beam. Their sum
    is zero, so I_emit = I_d + I_keeper + I_interstage. The beam-neutralizing electrons are part of I_d, not added to it.
    """
    I_d = _num("I_d_A", I_d_A, lo=0.0, lo_open=True)
    I_b = _num("I_beam_A", I_beam_A, lo=0.0)
    I_k = _num("I_keeper_A", I_keeper_A, lo=0.0)
    I_x = _num("I_interstage_A", I_interstage_A)
    I_emit = I_d + I_k + I_x
    if I_emit <= 0.0:
        raise CathodeIntegrationError(f"cathode emission I_d + I_keeper + I_interstage = {I_emit} A must be positive")
    if I_b > I_d + I_x:
        raise CathodeIntegrationError(
            f"beam current {I_b} A exceeds the cathode's net emission into the discharge and interstage circuits "
            f"(I_d + I_interstage = {I_d + I_x} A): the plume could not be current-free")
    plasma_node_sum = I_d + I_k + I_x - I_emit + (-I_b + I_b)
    return {
        "I_emit_A": I_emit,
        "I_discharge_A": I_d,
        "I_plume_neutralization_A": I_b,
        "I_emit_minus_neutralization_A": I_emit - I_b,
        "I_keeper_A": I_k,
        "I_interstage_A": I_x,
        "current_utilization_Ib_over_Id": I_b / I_d,
        "kirchhoff_residual_A": plasma_node_sum,
    }


def discharge_current_bounds_A(thrust_N: float, mdot_total_kg_s: float, V_d_V: float, P_other_to_jet_W: float,
                               P_available_for_discharge_W: float) -> dict:
    """Hall-closure-free envelope for I_d.

    lower: T <= sqrt(2 mdot P_jet) (Cauchy-Schwarz over the exhaust) and P_jet <= I_d V_d + P_other, so
           I_d >= (T^2/(2 mdot) - P_other)/V_d (clipped at 0);
    upper: I_d <= P_available_for_discharge / V_d.
    """
    T = _num("thrust_N", thrust_N, lo=0.0, lo_open=True)
    md = _num("mdot_total_kg_s", mdot_total_kg_s, lo=0.0, lo_open=True)
    V = _num("V_d_V", V_d_V, lo=0.0, lo_open=True)
    Po = _num("P_other_to_jet_W", P_other_to_jet_W, lo=0.0)
    Pa = _num("P_available_for_discharge_W", P_available_for_discharge_W, lo=0.0)
    P_jet_min = T * T / (2.0 * md)
    lower = max(0.0, (P_jet_min - Po) / V)
    upper = Pa / V
    return {"I_d_lower_A": lower, "I_d_upper_A": upper, "P_jet_min_W": P_jet_min, "feasible": lower <= upper}


def cathode_xe_flow_mg_s(law: str, value: float, anode_mdot_mg_s: float | None) -> float:
    if law not in FLOW_LAWS:
        raise CathodeIntegrationError(f"unknown cathode flow law {law!r}; expected one of {FLOW_LAWS}")
    if law == "fixed_mg_s":
        if anode_mdot_mg_s is not None:
            raise CathodeIntegrationError("fixed_mg_s flow law takes no anode flow (ambiguous input)")
        return _num("cathode flow (mg/s)", value, lo=0.0)
    if anode_mdot_mg_s is None:
        raise CathodeIntegrationError("fraction_of_anode_flow needs the anode mass flow")
    frac = _num("cathode/anode flow fraction", value, lo=0.0)
    return frac * _num("anode_mdot_mg_s", anode_mdot_mg_s, lo=0.0)


def mission_cathode_xe_kg(flow_mg_s: float, firing_h: float, starts: float, ignition_flow_mg_s: float,
                          ignition_duration_s: float, standby_flow_mg_s: float, standby_h: float) -> dict:
    """Cathode Xe over the mission: firing + ignition (per start) + standby. All terms explicit."""
    f = _num("flow_mg_s", flow_mg_s, lo=0.0)
    th = _num("firing_h", firing_h, lo=0.0)
    n = _num("starts", starts, lo=0.0)
    fi = _num("ignition_flow_mg_s", ignition_flow_mg_s, lo=0.0)
    ti = _num("ignition_duration_s", ignition_duration_s, lo=0.0)
    fs = _num("standby_flow_mg_s", standby_flow_mg_s, lo=0.0)
    ts = _num("standby_h", standby_h, lo=0.0)
    firing = f * th * SECONDS_PER_HOUR / MG_PER_KG
    ignition = fi * ti * n / MG_PER_KG
    standby = fs * ts * SECONDS_PER_HOUR / MG_PER_KG
    return {"firing_kg": firing, "ignition_kg": ignition, "standby_kg": standby, "total_kg": firing + ignition + standby}


def max_cathode_flow_for_mass_mg_s(mass_kg: float, firing_h: float) -> float:
    """Constant cathode flow that consumes ``mass_kg`` of Xe over ``firing_h`` of firing."""
    m = _num("mass_kg", mass_kg, lo=0.0)
    th = _num("firing_h", firing_h, lo=0.0, lo_open=True)
    return m * MG_PER_KG / (th * SECONDS_PER_HOUR)


def mg_s_to_sccm(mdot_mg_s: float, mg_s_per_sccm: float) -> float:
    return _num("mdot_mg_s", mdot_mg_s, lo=0.0) / _num("mg_s_per_sccm", mg_s_per_sccm, lo=0.0, lo_open=True)


def ram_number_flux_m2_s(n_m3: float, v_rel_m_s: float) -> float:
    """Directed number flux onto a ram-facing surface, n*v (thermal spread neglected; speed ratio >> 1)."""
    return _num("n_m3", n_m3, lo=0.0) * _num("v_rel_m_s", v_rel_m_s, lo=0.0)


def flux_equivalent_pressure_Pa(flux_m2_s: float, particle_mass_kg: float, T_ref_K: float) -> float:
    """Pressure of a Maxwellian gas at T_ref whose one-sided wall flux equals ``flux``.

    One-sided flux = n v_mean / 4 with v_mean = sqrt(8kT/(pi m)) (Goebel & Katz 2008, Eqs. 3.4-8, 3.4-12), p = n k T,
    hence p = flux * sqrt(2 pi m k T).
    """
    G = _num("flux_m2_s", flux_m2_s, lo=0.0)
    m = _num("particle_mass_kg", particle_mass_kg, lo=0.0, lo_open=True)
    T = _num("T_ref_K", T_ref_K, lo=0.0, lo_open=True)
    return G * math.sqrt(2.0 * math.pi * m * K_B * T)


def required_attenuation(p_external: float, p_tolerated: float) -> float:
    """Factor by which the cathode (Xe flow, orifice, keeper) must attenuate an external partial pressure/flux."""
    return _num("p_external", p_external, lo=0.0) / _num("p_tolerated", p_tolerated, lo=0.0, lo_open=True)


_OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b, ">": lambda a, b: a > b}


def _cond(name: str, x: float, cond: Mapping) -> bool:
    op = cond.get("op") if isinstance(cond, Mapping) else None
    if op not in _OPS:
        raise CathodeIntegrationError(f"evidence condition {name}: op {op!r} not in {sorted(_OPS)}")
    return _OPS[op](x, _num(f"{name}.value", cond.get("value")))


def oxygen_poisoning_screen(p_O2_Torr: float, T_emitter_K: float, evidence_points: Sequence[Mapping]) -> dict:
    """Place an (emitter O2 partial pressure, emitter temperature) state against the reported LaB6 O2 evidence.

    ``evidence_points`` come from the data file; each has ``id``, ``kind`` in {"no_degradation",
    "degradation_onset"} and two conditions ``T_K`` and ``p_O2_Torr`` of the form {"op": "<"|"<="|">="|">",
    "value": x}. This is an evidence lookup, not a poisoning model: a state that no point covers is reported as a gap.
    A degradation match wins over a no-degradation match.
    """
    p = _num("p_O2_Torr", p_O2_Torr, lo=0.0)
    T = _num("T_emitter_K", T_emitter_K, lo=0.0, lo_open=True)
    if not evidence_points:
        raise CathodeIntegrationError("no O2 poisoning evidence points supplied")
    covered, degraded = [], []
    for ep in evidence_points:
        kind = ep.get("kind")
        if kind not in ("no_degradation", "degradation_onset"):
            raise CathodeIntegrationError(f"unknown evidence point kind {kind!r}")
        if _cond("T_K", T, ep.get("T_K")) and _cond("p_O2_Torr", p, ep.get("p_O2_Torr")):
            (covered if kind == "no_degradation" else degraded).append(ep["id"])
    if degraded:
        status = "IN_REPORTED_DEGRADATION_RANGE"
    elif covered:
        status = "WITHIN_REPORTED_NO_DEGRADATION"
    else:
        status = "NO_EVIDENCE_AT_THIS_STATE"
    return {"status": status, "supporting_points": covered, "degradation_points": degraded}


# ------------------------------------------------------------------------------------------------ bus boundary

def steady_cathode_boundary_loads_W(keeper: KeeperState, heater_steady_W: Sourced) -> dict:
    """Load-side steady power on the two cathode boundary components (bus-side conversion is the boundary lane's)."""
    if keeper.mode not in KEEPER_MODES:
        raise CathodeIntegrationError(f"keeper.mode {keeper.mode!r} not in {KEEPER_MODES}")
    if keeper.mode == "on":
        P_k = _s("keeper.I_keeper_A", keeper.I_keeper_A, "A", lo=0.0, lo_open=True) * \
            _s("keeper.V_keeper_V", keeper.V_keeper_V, "V", lo=0.0)
    else:
        if keeper.I_keeper_A is not None or keeper.V_keeper_V is not None:
            raise CathodeIntegrationError("keeper off_floating takes no keeper current/voltage (ambiguous input)")
        P_k = 0.0
    return {"cathode_keeper": P_k, "cathode_heater": _s("heater_steady_W", heater_steady_W, "W", lo=0.0)}


BOUNDARY_LEDGER_FUNCTIONS = ("ledger", "bus_power_ledger")   # contract name first, then the boundary lane's name


def to_boundary_ledger(arch: str, cathode_loads_W: Mapping[str, float], other_loads_W: Mapping[str, float],
                       efficiencies: Mapping[str, float]):
    """Put the cathode loads on the common bus-power boundary (``abep_sim.arch_boundary``, another lane).

    ``cathode_loads_W`` must hold exactly cathode_keeper and cathode_heater (from this module); ``other_loads_W`` holds
    every other component of ``arch`` from its own producer. The union must be the architecture's full component set,
    because the boundary ledger defaults nothing. The boundary module is imported lazily; a missing module, another
    boundary version or a missing ledger function raises a clear error.
    """
    _check_arch(arch)
    if set(cathode_loads_W) != set(CATHODE_BOUNDARY_COMPONENTS):
        raise CathodeIntegrationError(f"cathode loads must be exactly {CATHODE_BOUNDARY_COMPONENTS}, got {sorted(cathode_loads_W)}")
    overlap = set(cathode_loads_W) & set(other_loads_W)
    if overlap:
        raise CathodeIntegrationError(f"cathode components {sorted(overlap)} also given in other_loads_W (double booking)")
    loads = {**dict(other_loads_W), **dict(cathode_loads_W)}
    missing = set(boundary_components(arch)) - set(loads)
    extra = set(loads) - set(boundary_components(arch))
    if missing or extra:
        raise CathodeIntegrationError(f"{arch} boundary needs exactly {boundary_components(arch)}; "
                                      f"missing {sorted(missing)}, outside the {arch} boundary {sorted(extra)}")
    try:
        mod = importlib.import_module(BOUNDARY_MODULE)
    except ImportError as exc:
        raise CathodeIntegrationError(
            f"{BOUNDARY_MODULE} ({BOUNDARY_VERSION}) is not present in this checkout; the bus-side ledger is produced by "
            f"the bus-power boundary lane. Cathode loads remain load-side values.") from exc
    if getattr(mod, "BOUNDARY_VERSION", None) != BOUNDARY_VERSION:
        raise CathodeIntegrationError(f"{BOUNDARY_MODULE}.BOUNDARY_VERSION is {getattr(mod, 'BOUNDARY_VERSION', None)!r}, "
                                      f"expected {BOUNDARY_VERSION!r}")
    fn = next((getattr(mod, n) for n in BOUNDARY_LEDGER_FUNCTIONS if callable(getattr(mod, n, None))), None)
    if fn is None:
        raise CathodeIntegrationError(f"{BOUNDARY_MODULE} has none of the ledger functions {BOUNDARY_LEDGER_FUNCTIONS}")
    return fn(arch, loads, dict(efficiencies))


def startup_transient(arch: str, phases: Sequence[StartupPhase]) -> dict:
    """Load-side bus-power profile of an ordered start-up sequence (piecewise constant per phase)."""
    _check_arch(arch)
    if not phases:
        raise CathodeIntegrationError("start-up sequence has no phases")
    allowed = set(boundary_components(arch))
    names, profile = set(), []
    energy_J = {c: 0.0 for c in allowed}
    preion_on = False
    for ph in phases:
        if not isinstance(ph, StartupPhase):
            raise CathodeIntegrationError("start-up phases must be StartupPhase objects")
        if not ph.name or ph.name in names:
            raise CathodeIntegrationError(f"start-up phase name {ph.name!r} empty or duplicated")
        names.add(ph.name)
        dt = _s(f"{ph.name}.duration_s", ph.duration_s, "s", lo=0.0, lo_open=True)
        if not ph.loads_W:
            raise CathodeIntegrationError(f"start-up phase {ph.name!r} declares no loads")
        bad = set(ph.loads_W) - allowed
        if bad:
            raise CathodeIntegrationError(f"phase {ph.name!r}: components {sorted(bad)} are not on the {arch} boundary")
        loads = {c: _s(f"{ph.name}.{c}", q, "W", lo=0.0) for c, q in ph.loads_W.items()}
        if any(loads.get(c, 0.0) > 0.0 for c in PREIONIZER_COMPONENTS[arch]):
            preion_on = True
        for c, w in loads.items():
            energy_J[c] += w * dt
        profile.append({"phase": ph.name, "duration_s": dt, "total_W": sum(loads.values()), "loads_W": loads})
    if PREIONIZER_COMPONENTS[arch] and not preion_on:
        raise CathodeIntegrationError(f"{arch} start-up never powers its pre-ionizer {PREIONIZER_COMPONENTS[arch]}: "
                                      f"that is not a start-up of this architecture")
    peak = max(profile, key=lambda r: r["total_W"])
    total_J = sum(energy_J.values())
    cath_J = sum(energy_J[c] for c in CATHODE_BOUNDARY_COMPONENTS)
    return {
        "architecture": arch, "boundary_version": BOUNDARY_VERSION, "profile": profile,
        "peak_W": peak["total_W"], "peak_phase": peak["phase"],
        "cathode_share_of_peak": sum(peak["loads_W"].get(c, 0.0) for c in CATHODE_BOUNDARY_COMPONENTS) / peak["total_W"]
        if peak["total_W"] > 0 else 0.0,
        "duration_s": sum(r["duration_s"] for r in profile),
        "energy_Wh": total_J / SECONDS_PER_HOUR,
        "cathode_energy_Wh": cath_J / SECONDS_PER_HOUR,
        "energy_by_component_Wh": {c: e / SECONDS_PER_HOUR for c, e in sorted(energy_J.items()) if e > 0.0},
    }


# ------------------------------------------------------------------------------------------------ scenario evaluation

def _check_operating_point(op: DischargeOperatingPoint) -> None:
    if op.basis not in OPERATING_POINT_BASES:
        raise CathodeIntegrationError(f"operating-point basis {op.basis!r} not in {OPERATING_POINT_BASES}")
    if op.basis == "admitted_closure":
        if not op.closure_member_id:
            raise CathodeIntegrationError("admitted_closure basis needs closure_member_id")
        from . import hall_ensemble   # lazy: only when an admitted closure is claimed
        try:
            hall_ensemble.require_admitted(op.closure_member_id)
        except ValueError as exc:
            raise CathodeIntegrationError(f"Hall operating point refused: {exc}") from exc
    else:
        if op.closure_member_id is not None:
            raise CathodeIntegrationError(
                f"closure_member_id {op.closure_member_id!r} given with basis {op.basis!r}: a transport closure is a "
                f"performance source only when admitted (screening candidates never are)")
    if op.basis == "hardware_measurement":
        for nm, q in (("I_d_A", op.I_d_A), ("I_beam_A", op.I_beam_A)):
            if isinstance(q, Sourced) and q.evidence_class != "measured":
                raise CathodeIntegrationError(f"hardware_measurement basis: {nm} must be 'measured', got {q.evidence_class!r}")


def _interstage_current(arch: str, ic: InterstageCircuit | None) -> float:
    if arch == "hall_only":
        if ic is not None:
            raise CathodeIntegrationError("hall_only has no pre-ionizer / interstage circuit")
        return 0.0
    if ic is None:
        raise CathodeIntegrationError(f"{arch}: the interstage circuit topology must be declared explicitly")
    if ic.topology not in INTERSTAGE_TOPOLOGIES:
        raise CathodeIntegrationError(f"interstage topology {ic.topology!r} not in {INTERSTAGE_TOPOLOGIES}")
    if not ic.declared_by or not ic.declared_by.strip():
        raise CathodeIntegrationError("interstage topology needs declared_by (design document or evidence)")
    if ic.topology == "separately_biased":
        return _s("interstage.I_net_electron_A", ic.I_net_electron_A, "A")
    if ic.I_net_electron_A is not None:
        raise CathodeIntegrationError(f"topology {ic.topology!r} carries no separate interstage current: by Kirchhoff it "
                                      f"is zero (floating) or already inside I_d (discharge-circuit referenced)")
    return 0.0


def _collect_sourced(obj, prefix: str, out: dict) -> None:
    if isinstance(obj, Sourced):
        out[prefix] = {"value": obj.value, "unit": obj.unit, "source": obj.source, "evidence_class": obj.evidence_class}
    elif isinstance(obj, TBD):
        out[prefix] = {"TBD": obj.requires}
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            _collect_sourced(v, f"{prefix}.{k}", out)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            nm = getattr(v, "name", None) or str(i)
            _collect_sourced(v, f"{prefix}[{nm}]", out)
    elif hasattr(obj, "__dataclass_fields__"):
        for k in obj.__dataclass_fields__:
            _collect_sourced(getattr(obj, k), f"{prefix}.{k}" if prefix else k, out)


def evaluate_architecture(arch: str, inp: CathodeIntegrationInputs) -> dict:
    """Cathode integration result for one architecture. Every output traces to explicit inputs."""
    _check_arch(arch)
    if not isinstance(inp, CathodeIntegrationInputs):
        raise CathodeIntegrationError("inputs must be a CathodeIntegrationInputs object")
    op = inp.operating_point
    _check_operating_point(op)
    I_d = _s("operating_point.I_d_A", op.I_d_A, "A", lo=0.0, lo_open=True)
    I_b = _s("operating_point.I_beam_A", op.I_beam_A, "A", lo=0.0)
    I_x = _interstage_current(arch, inp.interstage)
    loads = steady_cathode_boundary_loads_W(inp.keeper, inp.heater_steady_W)
    I_k = _s("keeper.I_keeper_A", inp.keeper.I_keeper_A, "A", lo=0.0) if inp.keeper.mode == "on" else 0.0
    cur = electron_current_budget(I_d, I_b, I_k, I_x)

    # Hall-closure-free envelope: the operating point must sit inside it
    if isinstance(inp.envelope, TBD):
        env = {"TBD": inp.envelope.requires}
    else:
        e = inp.envelope
        env = discharge_current_bounds_A(_s("envelope.thrust_N", e.thrust_N, "N"),
                                         _s("envelope.mdot_total_kg_s", e.mdot_total_kg_s, "kg/s"),
                                         _s("envelope.V_d_V", e.V_d_V, "V"),
                                         _s("envelope.P_other_to_jet_W", e.P_other_to_jet_W, "W"),
                                         _s("envelope.P_available_for_discharge_W", e.P_available_for_discharge_W, "W"))
        if not env["feasible"]:
            raise CathodeIntegrationError(f"envelope infeasible: I_d lower bound {env['I_d_lower_A']:.4g} A exceeds the "
                                          f"power-limited upper bound {env['I_d_upper_A']:.4g} A")
        if not env["I_d_lower_A"] <= I_d <= env["I_d_upper_A"]:
            raise CathodeIntegrationError(f"I_d = {I_d} A outside the conservation/power envelope "
                                          f"[{env['I_d_lower_A']:.4g}, {env['I_d_upper_A']:.4g}] A")

    # Xe flow and mission Xe
    fl = inp.flow
    if fl.law == "fixed_mg_s":
        mdot_c = cathode_xe_flow_mg_s(fl.law, _s("flow.value", fl.value, "mg/s", lo=0.0), None)
    elif fl.law == "fraction_of_anode_flow":
        mdot_c = cathode_xe_flow_mg_s(fl.law, _s("flow.value", fl.value, "1", lo=0.0),
                                      _s("flow.anode_mdot_mg_s", fl.anode_mdot_mg_s, "mg/s", lo=0.0))
    else:
        raise CathodeIntegrationError(f"unknown cathode flow law {fl.law!r}")
    m = inp.mission
    mission_h = _s("mission.mission_h", m.mission_h, "h", lo=0.0, lo_open=True)
    firing_h = _s("mission.firing_h", m.firing_h, "h", lo=0.0)
    standby_h = _s("mission.standby_h", m.standby_h, "h", lo=0.0)
    if firing_h + standby_h > mission_h:
        raise CathodeIntegrationError(f"firing_h + standby_h = {firing_h + standby_h} h exceeds mission_h = {mission_h} h")
    xe = mission_cathode_xe_kg(mdot_c, firing_h, _s("mission.starts", m.starts, "1", lo=0.0),
                               _s("mission.ignition_flow_mg_s", m.ignition_flow_mg_s, "mg/s", lo=0.0),
                               _s("mission.ignition_duration_s", m.ignition_duration_s, "s", lo=0.0),
                               _s("mission.standby_flow_mg_s", m.standby_flow_mg_s, "mg/s", lo=0.0), standby_h)
    required_h = _s("mission.required_firing_h", m.required_firing_h, "h", lo=0.0, lo_open=True)

    # emitter temperature and evaporation-limited life (thermionic emission = I_emit, Schottky and backflow neglected
    # as in the IEPC-2017-276 life model)
    em = inp.emitter
    area = _s("emitter.emitting_area_cm2", em.emitting_area_cm2, "cm2", lo=0.0, lo_open=True)
    A = _s("emitter.richardson_A_A_cm2K2", em.richardson_A_A_cm2K2, "A/cm2/K2", lo=0.0, lo_open=True)
    phi0 = _s("emitter.work_function_eV", em.work_function_eV, "eV", lo=0.0, lo_open=True)
    alpha = _s("emitter.work_function_T_coeff_eV_K", em.work_function_T_coeff_eV_K, "eV/K")
    J = cur["I_emit_A"] / area
    T_u = emitter_temperature_K(J, A, phi0, alpha, T_min_K=T_SEARCH_MIN_K, T_max_K=T_SEARCH_MAX_K)
    dT = _s("emitter.peak_temperature_offset_K", em.peak_temperature_offset_K, "K", lo=0.0)
    B = _s("emitter.evaporation_B_K", em.evaporation_B_K, "K", lo=0.0, lo_open=True)
    C = _s("emitter.evaporation_C", em.evaporation_C, "1")
    life_h = evaporation_limited_life_h(T_u + dT, B, C,
                                        _s("emitter.insert_density_g_cm3", em.insert_density_g_cm3, "g/cm3", lo=0.0, lo_open=True),
                                        _s("emitter.usable_thickness_cm", em.usable_thickness_cm, "cm", lo=0.0, lo_open=True),
                                        _s("emitter.redeposition_fraction", em.redeposition_fraction, "1", lo=0.0, hi=1.0))
    emitter = {"J_A_cm2": J, "T_uniform_K": T_u, "T_evaporation_K": T_u + dT,
               "evaporation_g_cm2_s": lafferty_evaporation_rate_g_cm2_s(T_u + dT, B, C),
               "life_h": life_h, "life_margin_vs_required_firing": life_h / required_h}

    # poisoning (evidence lookup; atomic O and N2 have no quantitative evidence in the accessed sources)
    po = inp.poisoning
    T_cold = T_u - _s("poisoning.cold_region_temperature_offset_K", po.cold_region_temperature_offset_K, "K", lo=0.0)
    if T_cold <= 0.0:
        raise CathodeIntegrationError(f"cold-region offset leaves a non-physical screening temperature {T_cold} K")
    if isinstance(po.p_O2_equiv_at_emitter_Torr, TBD):
        pois = {"O2": {"status": "TBD", "requires": po.p_O2_equiv_at_emitter_Torr.requires}}
    else:
        pois = {"O2": {**oxygen_poisoning_screen(_s("poisoning.p_O2_equiv_at_emitter_Torr", po.p_O2_equiv_at_emitter_Torr,
                                                    "Torr", lo=0.0), T_cold, po.evidence_points),
                       "T_screen_K": T_cold}}
    for sp in po.other_species_at_emitter:
        if sp == "O2":
            raise CathodeIntegrationError("O2 is screened through p_O2_equiv_at_emitter_Torr, not other_species_at_emitter")
        pois[sp] = {"status": "NO_QUANTITATIVE_EVIDENCE",
                    "requires": f"a published LaB6 emission-degradation threshold for {sp} (none in the accessed sources)"}

    st = startup_transient(arch, inp.startup)

    ev: dict = {}
    _collect_sourced(inp, "", ev)
    classes = sorted({v["evidence_class"] for v in ev.values() if "evidence_class" in v})
    assumed = sorted(k for k, v in ev.items() if v.get("evidence_class") == "assumed")
    tbd = sorted(k for k, v in ev.items() if "TBD" in v)
    absolute = op.basis in ("admitted_closure", "hardware_measurement")
    milestones = ["A"]
    if absolute and not assumed and not tbd and all(r.get("status") not in ("TBD", "NO_QUANTITATIVE_EVIDENCE")
                                                    for r in pois.values()):
        milestones.append("B")
    return {
        "version": CATHODE_INTEGRATION_VERSION,
        "architecture": arch,
        "boundary_version": BOUNDARY_VERSION,
        "operating_point_basis": op.basis,
        "absolute_performance_claim": absolute,
        "milestone_support": milestones,
        "milestone_C": "not supported by this module alone: needs thermal_life integration, measured start-up and "
                       "keeper/heater data on the selected cathode, life/wear test and mission closure",
        "electron_current": cur,
        "discharge_current_envelope": env,
        "xe": {"cathode_flow_mg_s": mdot_c, "flow_law": fl.law, **xe},
        "boundary_loads_steady_W": loads,
        "startup": st,
        "emitter": emitter,
        "poisoning": pois,
        "evidence": {"inputs": ev, "classes_present": classes, "assumed_inputs": assumed, "tbd_inputs": tbd},
    }


def compare_architectures(results: Mapping[str, dict], *, rel_tol: float, xe_budget_kg: Sourced,
                          bus_power_limit_W: Sourced, dominance_fraction: Sourced) -> dict:
    """Side-by-side cathode quantities and conditional statements. Never ranks and never declares a winner.

    ``dominance_fraction`` is an owner (PROPOSED) threshold, not an RFP value: a cathode quantity above that fraction of
    the corresponding budget is flagged as 'could dominate'. A flag present in every architecture is labelled
    common-mode (not a discriminator).
    """
    tol = _num("rel_tol", rel_tol, lo=0.0)
    budget = _s("xe_budget_kg", xe_budget_kg, "kg", lo=0.0, lo_open=True)
    plim = _s("bus_power_limit_W", bus_power_limit_W, "W", lo=0.0, lo_open=True)
    frac = _s("dominance_fraction", dominance_fraction, "1", lo=0.0, lo_open=True, hi=1.0)
    if not results:
        raise CathodeIntegrationError("no architecture results to compare")
    for a, r in results.items():
        _check_arch(a)
        if r.get("architecture") != a or r.get("version") != CATHODE_INTEGRATION_VERSION:
            raise CathodeIntegrationError(f"result for {a!r} is not a {CATHODE_INTEGRATION_VERSION} result for {a!r}")
    bases = {r["operating_point_basis"] for r in results.values()}
    keys = {
        "I_emit_A": lambda r: r["electron_current"]["I_emit_A"],
        "I_interstage_A": lambda r: r["electron_current"]["I_interstage_A"],
        "cathode_flow_mg_s": lambda r: r["xe"]["cathode_flow_mg_s"],
        "cathode_xe_total_kg": lambda r: r["xe"]["total_kg"],
        "keeper_steady_W": lambda r: r["boundary_loads_steady_W"]["cathode_keeper"],
        "heater_steady_W": lambda r: r["boundary_loads_steady_W"]["cathode_heater"],
        "startup_peak_W": lambda r: r["startup"]["peak_W"],
        "startup_cathode_energy_Wh": lambda r: r["startup"]["cathode_energy_Wh"],
        "T_evaporation_K": lambda r: r["emitter"]["T_evaporation_K"],
        "insert_life_h": lambda r: r["emitter"]["life_h"],
    }
    table, differs = {}, {}
    for k, get in keys.items():
        vals = {a: get(r) for a, r in results.items()}
        table[k] = vals
        v = list(vals.values())
        ref = max(abs(x) for x in v)
        differs[k] = bool(ref > 0 and (max(v) - min(v)) > tol * ref)
    flags = {}
    for a, r in results.items():
        f = []
        if r["xe"]["total_kg"] > frac * budget:
            f.append("cathode_xe_could_dominate_xe_budget")
        if sum(r["boundary_loads_steady_W"].values()) > frac * plim:
            f.append("cathode_steady_power_could_dominate_bus_limit")
        if r["startup"]["peak_W"] > plim:
            f.append("startup_peak_exceeds_bus_limit")
        flags[a] = f
    all_flags = set().union(*flags.values()) if flags else set()
    common = sorted(fl for fl in all_flags if all(fl in v for v in flags.values()))
    statements = []
    for k, d in differs.items():
        if d:
            statements.append(f"IF the inputs are as given THEN {k} differs between architectures: {table[k]}")
    for fl in common:
        statements.append(f"IF the inputs are as given THEN '{fl}' holds for every architecture: common-mode, "
                          f"not a discriminator")
    for a, f in flags.items():
        for fl in f:
            if fl not in common:
                statements.append(f"IF the inputs are as given THEN '{fl}' holds for {a} only")
    return {
        "version": CATHODE_INTEGRATION_VERSION,
        "operating_point_bases": sorted(bases),
        "conditional": bool(bases & {"conditional_scenario"}) or any(r["evidence"]["assumed_inputs"] for r in results.values()),
        "table": table, "differs": differs, "flags": flags, "common_mode_flags": common,
        "thresholds": {"xe_budget_kg": xe_budget_kg.__dict__, "bus_power_limit_W": bus_power_limit_W.__dict__,
                       "dominance_fraction": dominance_fraction.__dict__, "rel_tol": tol},
        "statements": statements,
        "ranking": None,   # deliberately never produced
    }


# ------------------------------------------------------------------------------------------------ data file

_REQUIRED_PARAM_FIELDS = ("value", "unit", "source_id", "locator", "evidence_level", "quantity_type", "uncertainty",
                          "applicability_domain", "validation_status", "transformation_chain")
_ACCESS = ("open_full_text", "abstract_only", "metadata_only", "repo_frozen", "not_accessed", "lane_derivation")


def load_data(path: str | None = None) -> dict:
    p = path if path is not None else DATA_FILE
    if not os.path.isfile(p):
        raise CathodeIntegrationError(f"cathode integration data file not found: {p}")
    with open(p) as fh:
        d = json.load(fh)
    errors = validate_data(d)
    if errors:
        raise CathodeIntegrationError("cathode integration data file invalid:\n  " + "\n  ".join(errors))
    return d


def validate_data(d: Mapping) -> list:
    """Evidence-discipline checks on the data file. Returns a list of violations (empty = valid)."""
    err = []
    if d.get("id") != "cathode_integration_data_v1":
        err.append("id must be 'cathode_integration_data_v1'")
    if d.get("module_version") != CATHODE_INTEGRATION_VERSION:
        err.append(f"module_version must be {CATHODE_INTEGRATION_VERSION!r}")
    if tuple(d.get("architectures", ())) != ARCHITECTURES:
        err.append(f"architectures must be {list(ARCHITECTURES)}")
    b = d.get("boundary", {})
    if b.get("version") != BOUNDARY_VERSION or tuple(b.get("cathode_components", ())) != CATHODE_BOUNDARY_COMPONENTS:
        err.append("boundary must name bus_power_boundary_v1 and components cathode_keeper, cathode_heater")
    sources = d.get("sources", {})
    if not sources:
        err.append("no sources")
    for sid, s in sources.items():
        for f in ("citation", "access"):
            if not s.get(f):
                err.append(f"source {sid}: missing {f}")
        if s.get("access") not in _ACCESS:
            err.append(f"source {sid}: access {s.get('access')!r} not in {_ACCESS}")
        if s.get("access") == "open_full_text" and not (s.get("url") and s.get("sha256")):
            err.append(f"source {sid}: open_full_text needs url and sha256 of the accessed file")
        if s.get("access") in ("not_accessed", "metadata_only") and s.get("used_for_values", False):
            err.append(f"source {sid}: a source not read in full cannot supply values")
    params = d.get("parameters", {})
    for pid, p in params.items():
        for f in _REQUIRED_PARAM_FIELDS:
            if f not in p:
                err.append(f"parameter {pid}: missing {f}")
        if p.get("source_id") not in sources:
            err.append(f"parameter {pid}: source_id {p.get('source_id')!r} not in sources")
        elif sources[p["source_id"]].get("access") in ("not_accessed", "metadata_only", "abstract_only"):
            err.append(f"parameter {pid}: value taken from a source that was not read in full ({p['source_id']})")
        elif sources[p["source_id"]].get("access") == "lane_derivation" and not (
                "assumed" in p.get("quantity_type", "") or "model-derived" in p.get("quantity_type", "")):
            err.append(f"parameter {pid}: a lane value must be labelled assumed or model-derived")
        lvl = p.get("evidence_level")
        if not (isinstance(lvl, int) and 1 <= lvl <= 7):
            err.append(f"parameter {pid}: evidence_level must be an integer 1..7")
        qt = p.get("quantity_type", "")
        if not any(c in qt for c in EVIDENCE_CLASSES):
            err.append(f"parameter {pid}: quantity_type must name an evidence class {EVIDENCE_CLASSES}")
        v = p.get("value")
        if isinstance(v, str):
            if not v.startswith("TBD"):
                err.append(f"parameter {pid}: string value must be 'TBD — requires ...'")
        elif isinstance(v, list):
            if not v or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v):
                err.append(f"parameter {pid}: list value must be finite numbers")
        elif isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            err.append(f"parameter {pid}: value must be a finite number, a list of numbers or 'TBD — requires ...'")
    for rid, r in d.get("relations", {}).items():
        for f in ("expression", "source_id", "locator", "evidence_level", "quantity_type", "function"):
            if f not in r:
                err.append(f"relation {rid}: missing {f}")
        if r.get("source_id") not in sources:
            err.append(f"relation {rid}: source_id {r.get('source_id')!r} not in sources")
        fn = r.get("function")
        if fn and fn != "none" and not callable(globals().get(fn)):
            err.append(f"relation {rid}: function {fn!r} not defined in abep_sim.cathode_integration")
    eps = d.get("poisoning_evidence_points_O2", [])
    if not eps:
        err.append("no O2 poisoning evidence points")
    for i, ep in enumerate(eps):
        if not ep.get("id") or not ep.get("statement") or not ep.get("locator") or not ep.get("quantity_type"):
            err.append(f"poisoning evidence point {i}: needs id, statement, locator, quantity_type")
        if ep.get("source_id") not in sources:
            err.append(f"poisoning evidence point {i}: unknown source")
        if ep.get("kind") not in ("no_degradation", "degradation_onset"):
            err.append(f"poisoning evidence point {i}: unknown kind")
        for c in ("T_K", "p_O2_Torr"):
            cond = ep.get(c)
            if not isinstance(cond, Mapping) or cond.get("op") not in _OPS or isinstance(cond.get("value"), bool) \
                    or not isinstance(cond.get("value"), (int, float)):
                err.append(f"poisoning evidence point {i}: condition {c} must be {{op, value}}")
    for pid in d.get("reference_cathode_flows", []):
        if pid not in params:
            err.append(f"reference_cathode_flows: {pid!r} is not a parameter")
        elif params[pid].get("unit") != "mg/s":
            err.append(f"reference_cathode_flows: {pid!r} must be in mg/s")
    for t in d.get("proposed_thresholds", {}).values():
        if t.get("status") != "PROPOSED":
            err.append("every threshold that is not in the RFP must carry status PROPOSED")
    for t in d.get("tbd", []):
        if not str(t.get("requires", "")).startswith("TBD"):
            err.append(f"tbd item {t.get('id')}: requires must read 'TBD — requires ...'")
    return err


def parameter_value(d: Mapping, pid: str):
    """A sourced numeric parameter from the data file; refuses TBD values."""
    p = d["parameters"].get(pid)
    if p is None:
        raise CathodeIntegrationError(f"parameter {pid!r} not in the data file")
    if isinstance(p["value"], str):
        raise CathodeIntegrationError(f"parameter {pid!r} is {p['value']}")
    return p["value"]


def parameter_sourced(d: Mapping, pid: str, evidence_class: str, index: int | None = None) -> Sourced:
    """Wrap a data-file parameter as a Sourced input (``evidence_class`` names the quantity type of this use)."""
    v = parameter_value(d, pid)
    if isinstance(v, list):
        if index is None:
            raise CathodeIntegrationError(f"parameter {pid!r} is a list; pass index")
        v = v[index]
    p = d["parameters"][pid]
    if evidence_class not in p["quantity_type"]:
        raise CathodeIntegrationError(f"parameter {pid!r} quantity_type {p['quantity_type']!r} does not include "
                                      f"{evidence_class!r}")
    return Sourced(v, p["unit"], f"{p['source_id']}: {p['locator']}", evidence_class)


def poisoning_evidence_points(d: Mapping) -> tuple:
    return tuple(d["poisoning_evidence_points_O2"])


def cathode_dossier_path(repo_root: str | None = None) -> str:
    """The cathode evidence dossier (another lane), resolved lazily; raises if it is not in this checkout."""
    root = repo_root if repo_root is not None else REPO_ROOT
    p = os.path.join(root, CATHODE_DOSSIER_DIR_REL)
    if not os.path.isdir(p):
        raise CathodeIntegrationError(f"{CATHODE_DOSSIER_DIR_REL}/ (cathode evidence dossier lane) is not present in "
                                      f"this checkout; cathode evidence here comes from cathode_integration_data_v1.json only")
    return p


# ------------------------------------------------------------------------------------------------ derived statements

def derive_conditional_statements(d: Mapping, ambient: Sequence[Mapping]) -> dict:
    """Deterministic conditional statements from the sourced data file (written by the lane's derive script).

    ``ambient`` rows (alt_km, solar, n_O_m3, V_m_s, source) come from the frozen atmosphere dataset via the script.
    Only sourced parameters and RFP values enter; nothing is an operating-point claim.
    """
    errors = validate_data(d)
    if errors:
        raise CathodeIntegrationError("data file invalid: " + "; ".join(errors))
    rfp = d["rfp"]
    t_req = rfp["firing_h_min"]["value"]
    t_mis = rfp["mission_h"]["value"]
    m_lim = rfp["mass_max_kg"]["value"]
    out: dict = {"id": "cathode_integration_derived_v1", "module_version": CATHODE_INTEGRATION_VERSION,
                 "generated_by": "docs/architecture_comparison/cathode_integration/derive_cathode_integration_v1.py",
                 "data_file": "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
                 "nature": "conditional statements from sourced values; no operating point, no Hall prediction"}

    # 1. cathode Xe mass against the RFP mass limit
    mdot_all = max_cathode_flow_for_mass_mg_s(m_lim, t_req)
    rows = []
    for pid in d["reference_cathode_flows"]:
        p = d["parameters"][pid]
        vals = p["value"] if isinstance(p["value"], list) else [p["value"]]
        for v in vals:
            x = mission_cathode_xe_kg(v, t_req, 0.0, 0.0, 0.0, 0.0, 0.0)["total_kg"]
            x_all = mission_cathode_xe_kg(v, t_req, 0.0, 0.0, 0.0, v, t_mis - t_req)["total_kg"]
            rows.append({"parameter": pid, "flow_mg_s": v,
                         "flow_sccm": mg_s_to_sccm(v, parameter_value(d, "xe_mg_s_per_sccm")),
                         "xe_kg_over_min_firing": x, "fraction_of_rfp_mass_limit": x / m_lim,
                         "xe_kg_if_flowing_whole_mission": x_all,
                         "statement": f"IF the cathode flows {v} mg/s for the {t_req:.0f} h RFP minimum firing THEN it "
                                      f"uses {x:.2f} kg Xe ({x / m_lim:.1%} of the {m_lim:.0f} kg RFP system mass "
                                      f"limit, tank excluded)"})
    out["xe_mass_vs_rfp"] = {
        "flow_consuming_whole_mass_limit_mg_s": mdot_all,
        "relation": f"cathode flow that uses a fraction f of {m_lim:.0f} kg in {t_req:.0f} h = f x {mdot_all:.5f} mg/s",
        "reference_flows": rows}

    # 2. Richardson / Lafferty consistency and areal mass needed per unit life
    A29 = parameter_value(d, "lab6_richardson_A_lafferty")
    phi_l = parameter_value(d, "lab6_work_function_lafferty_iepc2017")
    A120 = parameter_value(d, "lab6_richardson_A_universal_gk")
    phi0 = parameter_value(d, "lab6_work_function_T_linear_phi0_gk")
    alpha = parameter_value(d, "lab6_work_function_T_linear_alpha_gk")
    B = parameter_value(d, "lab6_evaporation_B_lafferty")
    C = parameter_value(d, "lab6_evaporation_C_lafferty")
    em = []
    for J in parameter_value(d, "lab6_reference_current_densities"):
        T1 = emitter_temperature_K(J, A29, phi_l, 0.0, T_min_K=T_SEARCH_MIN_K, T_max_K=T_SEARCH_MAX_K)
        T2 = emitter_temperature_K(J, A120, phi0, alpha, T_min_K=T_SEARCH_MIN_K, T_max_K=T_SEARCH_MAX_K)
        W1 = lafferty_evaporation_rate_g_cm2_s(T1, B, C)
        em.append({"J_A_cm2": J, "T_K_lafferty_A29_phi2.67": T1, "T_K_gk_A120_phi_linear": T2,
                   "evaporation_g_cm2_s_at_T_lafferty": W1,
                   "areal_mass_evaporated_over_min_firing_g_cm2": W1 * t_req * SECONDS_PER_HOUR,
                   "statement": f"IF a uniform LaB6 insert emits {J} A/cm2 (T = {T1:.0f} K with A = 29, phi = {phi_l} eV) "
                                f"THEN, without redeposition, {W1 * t_req * SECONDS_PER_HOUR:.3g} g/cm2 evaporates in "
                                f"{t_req:.0f} h; insert areal mass (density x usable thickness) must exceed this"})
    T_stmt = parameter_value(d, "lab6_10Acm2_temperature_statement_C") + CELSIUS_TO_KELVIN
    J_at_stmt = richardson_current_density_A_cm2(T_stmt, A29, phi_l, 0.0)
    out["emitter_relations"] = {
        "rows": em,
        "consistency_check": {"statement_source": "lab6_10Acm2_temperature_statement_C",
                              "T_K": T_stmt, "J_A_cm2_from_lafferty_parameters": J_at_stmt,
                              "consistent_with_over_10_A_cm2": J_at_stmt > 10.0}}

    # 3. start-up heater energy from the reported heater power / time pairs
    hp = parameter_value(d, "hc1_heater_power_W")
    ht = parameter_value(d, "hc1_heating_time_s")
    out["startup_heater_energy"] = [
        {"heater_W": w, "time_s": s, "energy_Wh": w * s / SECONDS_PER_HOUR,
         "statement": f"IF a cathode needs {w} W for {s} s of preheat (Sitael HC1, emitter ~1460 K) THEN each start "
                      f"costs {w * s / SECONDS_PER_HOUR:.2f} Wh on cathode_heater; the mission total scales with the "
                      f"number of starts (TBD)"} for w, s in zip(hp, ht)]

    # 4. ambient atomic-oxygen ram flux, expressed as a flux-equivalent pressure (scale only; no O threshold exists)
    T_ref = parameter_value(d, "poisoning_flux_equivalence_T_ref_K")
    m_O = parameter_value(d, "atomic_oxygen_mass_kg")
    amb = []
    for row in ambient:
        G = ram_number_flux_m2_s(row["n_O_m3"], row["V_m_s"])
        p = flux_equivalent_pressure_Pa(G, m_O, T_ref)
        amb.append({**row, "ram_flux_m2_s": G, "flux_equivalent_p_Pa": p, "flux_equivalent_p_Torr": p / TORR_TO_PA})
    out["ambient_atomic_oxygen"] = {
        "T_ref_K": T_ref, "rows": amb,
        "caveat": "ram-facing external surface, directed flux only; the emitter sits inside the cathode behind the Xe "
                  "flow and orifice (attenuation TBD). No published LaB6 threshold for atomic O was found, so these "
                  "values are NOT compared with the O2 thresholds; they only show the scale the shielding must handle."}
    return out
