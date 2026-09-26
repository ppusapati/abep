"""Architecture break-even relations: can a pre-ionizer (rf_hall, ecr_hall) pay for itself against hall_only?

Pure functions, no absolute Hall prediction. Every physical/efficiency input is explicit; nothing has a default value;
missing, non-finite or out-of-domain inputs raise ``BreakevenInputError`` (CLAUDE.md rule 3). Not wired into
``archengine`` (wiring would be a model change; the goldens must not move).

Derivation, sources and assumptions: docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md. Surfaces over
analysis ranges: scripts/architecture/build_breakeven_surfaces.py -> docs/architecture_comparison/breakeven/.

Model (0-D efficiency decomposition, Hofer & Gallimore AIAA-2004-3602 Eqs. 2-8; Goebel & Katz 2008 Eqs. 2.3-16,
7.3-10/11/16) generalised to two ion populations in the common Hall beam:
  H  ions born in the Hall discharge (beam current I_H, mix mix_H),
  S  ions delivered by the pre-ionizer and accelerated in the Hall (I_S = eta_transport * I_src, mix mix_S).
With u_H, u_S the mass-utilization shares (u = I * mu / mdot, mu = mass per coulomb of the mix):
  T   = gamma * sqrt(V_d) * mdot * N,   N = sqrt(eta_v) theta_H u_H + sqrt(eta_v_S) theta_S u_S
  P_d = V_d * mdot * D,                 D = rho_H u_H / eta_b + rho_S u_S / eta_b_S
  eta_a = T^2 / (2 mdot P_d) = gamma^2 N^2 / (2 D)        (independent of V_d and mdot)
  1/eta_b_S = 1 + (1 - chi) (1/eta_b - 1)                 chi in [0, 1]: Hall electron-current overhead avoided per S ion
  u_H = eta_u0 - (1 - alpha) u_S, eta_u1 = eta_u0 + alpha u_S   alpha in [0, 1]: additionality of S ions
For one population and one element this reduces exactly to eta_a = gamma^2 eta_q eta_v eta_b eta_m (Hofer Eq. 4-5).

Master power break-even (bus_power_boundary_v1; identical for the equal-thrust and equal-bus-power conventions):
  eta_a1 / eta_a0 >= 1 / (1 - omega),   omega = O / P_d_bus0,
  O = source bus power (+ ecr_magnet) + interstage loss + extra PPU + change of common-component bus power.
"""
from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .constants import AMU, E_CHARGE

BREAKEVEN_VERSION = "breakeven_v1"
BOUNDARY_VERSION = "bus_power_boundary_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
PREIONIZED_ARCHITECTURES = ("rf_hall", "ecr_hall")
# Component names of the shared bus-power boundary contract (abep_sim/arch_boundary.py, built by another lane).
COMMON_COMPONENTS = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
                     "thermal_control", "housekeeping")
COMMON_NON_DISCHARGE = tuple(c for c in COMMON_COMPONENTS if c != "hall_discharge")
SOURCE_COMPONENTS = {"rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}
GENERATOR_COMPONENT = {"rf_hall": "rf_source", "ecr_hall": "ecr_source"}
# Quantity types of docs/EVIDENCE.md. "TBD" is deliberately not accepted: a TBD quantity cannot be evaluated.
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
CONVENTIONS = ("equal_thrust", "equal_bus_power")
HARDWARE_KEYS = ("source_head", "source_generator_ppu", "source_magnets", "interstage", "thermal_added")
POWER_REFERENCES = {"bus": (), "forward": ("generator",), "absorbed": ("generator", "coupling")}
COST_UNITS = ("W_per_A", "eV_per_ion")
MILESTONE_SUPPORT = {
    "supports": ["A"],
    "A": "conditional selection: identifies regions where no pre-ionizer can pay for itself in power under the most "
         "favourable corner of the declared model family, and the conditions (utilization gain, ion cost, transport "
         "efficiency, overhead) an architecture must demonstrate to be baseline.",
    "to_reach_B": "admitted Hall transport closure(s) for Vyovrinda geometry giving eta_u0, eta_b, eta_v, gamma and "
                  "their V_d dependence per credible-set member; measured or closure-derived alpha, chi, eta_v_S and "
                  "delivered-ion mix; measured source ion cost and eta_transport on N2/O/O2 at the common feed state.",
    "to_reach_C": "power-system and thrust mass sensitivities, hardware masses, source and Hall life limits with "
                  "evidence, thermal closure (thermal_life.py), startup/cathode, integrated mission closure.",
}


class BreakevenInputError(ValueError):
    """Missing, non-finite or out-of-domain input (no silent fallback)."""


class BreakevenContractError(RuntimeError):
    """A shared-contract module (e.g. abep_sim/arch_boundary.py) is missing or has another version."""


def _num(name: str, x, lo: float | None = None, hi: float | None = None, lo_open: bool = False,
         hi_open: bool = False) -> float:
    if x is None:
        raise BreakevenInputError(f"{name} is required (got None); no default is assumed")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise BreakevenInputError(f"{name} must be a real number, got {type(x).__name__}")
    x = float(x)
    if not math.isfinite(x):
        raise BreakevenInputError(f"{name} must be finite, got {x}")
    if lo is not None and (x < lo or (lo_open and x == lo)):
        raise BreakevenInputError(f"{name} = {x} is below its domain ({'(' if lo_open else '['}{lo}, ...)")
    if hi is not None and (x > hi or (hi_open and x == hi)):
        raise BreakevenInputError(f"{name} = {x} is above its domain (..., {hi}{')' if hi_open else ']'})")
    return x


def _keys(name: str, mapping, required: Sequence[str]) -> None:
    if not isinstance(mapping, Mapping):
        raise BreakevenInputError(f"{name} must be a mapping with keys {list(required)}")
    missing = [k for k in required if k not in mapping]
    extra = [k for k in mapping if k not in required]
    if missing or extra:
        raise BreakevenInputError(f"{name}: missing keys {missing}, unexpected keys {extra}; required exactly "
                                  f"{list(required)} (explicit zeros are allowed, omissions are not)")


# ----------------------------------------------------------------------------------------------------------------------
# Evidence-tagged values (mass, life and evidence-placement inputs)
@dataclass(frozen=True)
class Evidenced:
    value: float
    unit: str
    evidence_class: str
    source: str

    def __post_init__(self):
        _num(f"Evidenced({self.source!r}).value", self.value)
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise BreakevenInputError(f"evidence_class {self.evidence_class!r} not in {EVIDENCE_CLASSES}; a quantity "
                                      "that is still TBD cannot be evaluated")
        if not isinstance(self.source, str) or not self.source.strip():
            raise BreakevenInputError("every evidenced value needs a non-empty source")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise BreakevenInputError("every evidenced value needs a unit")


def _ev(name: str, x, unit: str) -> Evidenced:
    if not isinstance(x, Evidenced):
        raise BreakevenInputError(f"{name} must be an Evidenced value (value, unit, evidence_class, source)")
    if x.unit != unit:
        raise BreakevenInputError(f"{name}: unit {x.unit!r}, expected {unit!r}")
    return x


# ----------------------------------------------------------------------------------------------------------------------
# Ion populations
@dataclass(frozen=True)
class IonSpecies:
    label: str
    mass_amu: float
    charge: int
    current_fraction: float

    def __post_init__(self):
        if not isinstance(self.label, str) or not self.label:
            raise BreakevenInputError("ion species label is required")
        _num(f"{self.label}.mass_amu", self.mass_amu, lo=0.0, lo_open=True)
        if isinstance(self.charge, bool) or not isinstance(self.charge, int) or self.charge < 1:
            raise BreakevenInputError(f"{self.label}.charge must be an integer >= 1")
        _num(f"{self.label}.current_fraction", self.current_fraction, lo=0.0, hi=1.0, lo_open=True)


@dataclass(frozen=True)
class IonMix:
    """Beam-current composition of one ion population (fractions of that population's current, summing to 1)."""
    species: tuple

    def __post_init__(self):
        if not isinstance(self.species, tuple) or not self.species:
            raise BreakevenInputError("IonMix.species must be a non-empty tuple of IonSpecies")
        if any(not isinstance(s, IonSpecies) for s in self.species):
            raise BreakevenInputError("IonMix.species entries must be IonSpecies")
        labels = [s.label for s in self.species]
        if len(set(labels)) != len(labels):
            raise BreakevenInputError(f"duplicate species labels {labels}")
        tot = sum(s.current_fraction for s in self.species)
        if abs(tot - 1.0) > 1e-9:
            raise BreakevenInputError(f"current fractions sum to {tot}, not 1")

    @property
    def kg_per_coulomb(self) -> float:          # mu: ion mass flow per ampere of this population
        return sum(s.current_fraction * s.mass_amu * AMU / (s.charge * E_CHARGE) for s in self.species)

    @property
    def coulomb_per_kg(self) -> float:          # rho = 1/mu: beam current per unit ion mass flow
        return 1.0 / self.kg_per_coulomb

    @property
    def thrust_coefficient(self) -> float:      # kappa: T = gamma sqrt(eta_v V) kappa I   [sqrt(kg/C)]
        return sum(s.current_fraction * math.sqrt(2.0 * s.mass_amu * AMU / (s.charge * E_CHARGE)) for s in self.species)

    @property
    def velocity_coefficient(self) -> float:    # theta = kappa * rho: T = gamma sqrt(eta_v V) mdot_ion theta [sqrt(C/kg)]
        return self.thrust_coefficient * self.coulomb_per_kg

    @property
    def charge_factor(self) -> float:           # kappa^2 rho / 2; equals Hofer's eta_q (Eq. 5) for a single element
        return self.thrust_coefficient ** 2 * self.coulomb_per_kg / 2.0

    @property
    def mean_charge_per_ion(self) -> float:     # elementary charges per ion (for eV/ion <-> W/A)
        return 1.0 / sum(s.current_fraction / s.charge for s in self.species)


# ----------------------------------------------------------------------------------------------------------------------
# Hall-only reference and pre-ionizer response
@dataclass(frozen=True)
class HallReference:
    """Hall-only operating point on the common hardware. Analysis inputs, not predictions.

    eta_u: mass utilization (Hofer eta_m), eta_b: current utilization I_b/I_d, eta_v: voltage utilization (mean
    beam energy per charge / V_d, energy basis), gamma_div: momentum-weighted divergence factor (G&K F_t;
    eta_div = gamma^2), eta_ppu_discharge: bus -> discharge converter efficiency (common hardware, same in all arms).
    mdot_kg_s: total propellant flow through the Hall channel (common feed state; for an arm it passes the source).
    """
    mdot_kg_s: float
    V_d_V: float
    eta_u: float
    eta_b: float
    eta_v: float
    gamma_div: float
    eta_ppu_discharge: float
    mix: IonMix

    def __post_init__(self):
        _num("mdot_kg_s", self.mdot_kg_s, lo=0.0, lo_open=True)
        _num("V_d_V", self.V_d_V, lo=0.0, lo_open=True)
        for n in ("eta_u", "eta_b", "eta_v", "gamma_div", "eta_ppu_discharge"):
            _num(n, getattr(self, n), lo=0.0, hi=1.0, lo_open=True)
        if not isinstance(self.mix, IonMix):
            raise BreakevenInputError("HallReference.mix must be an IonMix")


@dataclass(frozen=True)
class PreionResponse:
    """How delivered ions interact with the common Hall (assumed model parameters until an admitted closure or a test
    supplies them). alpha: additionality (1 = S ions add to Hall-born ions; 0 = they replace them). chi: fraction of the
    Hall's per-ion electron-current overhead V_d (1/eta_b - 1) that an S ion avoids (0 = S ion costs the full Hall price
    V_d/eta_b; 1 = it costs only its own current, V_d). eta_v_delivered: voltage utilization of S ions. mix_delivered:
    S-ion beam composition."""
    alpha: float
    chi: float
    eta_v_delivered: float
    mix_delivered: IonMix

    def __post_init__(self):
        _num("alpha", self.alpha, lo=0.0, hi=1.0)
        _num("chi", self.chi, lo=0.0, hi=1.0)
        _num("eta_v_delivered", self.eta_v_delivered, lo=0.0, hi=1.0, lo_open=True)
        if not isinstance(self.mix_delivered, IonMix):
            raise BreakevenInputError("PreionResponse.mix_delivered must be an IonMix")


@dataclass(frozen=True)
class BusOverhead:
    """Bus-referred power the pre-ionized arm adds relative to hall_only, excluding the hall_discharge term, which the
    model computes. source_bus_W: exactly the arch's source components (rf_hall: rf_source; ecr_hall: ecr_source,
    ecr_magnet). delta_common_bus_W: arm minus hall_only for every common component other than hall_discharge
    (explicit zeros allowed). interstage_loss_bus_W: bus power of coupling hardware between source and Hall (bias,
    guide field; ion loss is in eta_transport and in the source load, not here). extra_ppu_bus_W: fixed losses of
    added power processing not already inside the component bus powers.

    Mapping onto bus_power_boundary_v1 (which has exactly the component set above and no extra keys): supply fixed
    overheads are inside the source component's efficiency, added PPU control/standby is booked under housekeeping
    (delta_common_bus_W['housekeeping']), and an interstage consumer has no v1 component. A v1-conformant overhead
    therefore has interstage_loss_bus_W = extra_ppu_bus_W = 0 (see boundary_v1_conformant); non-zero values are
    sensitivity terms outside v1."""
    arch: str
    source_bus_W: Mapping[str, float]
    delta_common_bus_W: Mapping[str, float]
    interstage_loss_bus_W: float
    extra_ppu_bus_W: float

    def __post_init__(self):
        if self.arch not in PREIONIZED_ARCHITECTURES:
            raise BreakevenInputError(f"arch {self.arch!r}: a break-even overhead exists only for "
                                      f"{PREIONIZED_ARCHITECTURES} (hall_only is the reference)")
        _keys(f"{self.arch}.source_bus_W", self.source_bus_W, SOURCE_COMPONENTS[self.arch])
        for k, v in self.source_bus_W.items():
            _num(f"source_bus_W[{k}]", v, lo=0.0)
        _keys("delta_common_bus_W", self.delta_common_bus_W, COMMON_NON_DISCHARGE)
        for k, v in self.delta_common_bus_W.items():
            _num(f"delta_common_bus_W[{k}]", v)
        _num("interstage_loss_bus_W", self.interstage_loss_bus_W, lo=0.0)
        _num("extra_ppu_bus_W", self.extra_ppu_bus_W, lo=0.0)

    @property
    def boundary_v1_conformant(self) -> bool:
        return self.interstage_loss_bus_W == 0.0 and self.extra_ppu_bus_W == 0.0

    @property
    def generator_W(self) -> float:             # the plasma generator itself (rf_source / ecr_source)
        return float(self.source_bus_W[GENERATOR_COMPONENT[self.arch]])

    @property
    def fixed_W(self) -> float:                 # everything that does not scale with ions produced
        return self.total_W - self.generator_W

    @property
    def total_W(self) -> float:
        return float(sum(self.source_bus_W.values()) + sum(self.delta_common_bus_W.values())
                     + self.interstage_loss_bus_W + self.extra_ppu_bus_W)

    def ledger_lines(self) -> dict:
        lines = {k: float(v) for k, v in self.source_bus_W.items()}
        lines.update({f"delta_{k}": float(v) for k, v in self.delta_common_bus_W.items()})
        lines["interstage_loss"] = float(self.interstage_loss_bus_W)
        lines["extra_ppu"] = float(self.extra_ppu_bus_W)
        return lines


def overhead_from_ledgers(arch: str, arm_bus_W: Mapping[str, float], hall_only_bus_W: Mapping[str, float],
                          interstage_loss_bus_W: float, extra_ppu_bus_W: float) -> BusOverhead:
    """Build the overhead from two per-component bus ledgers (as bus_power_boundary_v1 would produce them). Both
    ledgers must list every component of their architecture; hall_discharge is excluded (computed by this module)."""
    if arch not in PREIONIZED_ARCHITECTURES:
        raise BreakevenInputError(f"arch {arch!r} not in {PREIONIZED_ARCHITECTURES}")
    _keys("hall_only_bus_W", hall_only_bus_W, COMMON_COMPONENTS)
    _keys(f"{arch}_bus_W", arm_bus_W, COMMON_COMPONENTS + SOURCE_COMPONENTS[arch])
    for d in (hall_only_bus_W, arm_bus_W):
        for k, v in d.items():
            _num(f"ledger[{k}]", v, lo=0.0)
    return BusOverhead(arch=arch, source_bus_W={k: arm_bus_W[k] for k in SOURCE_COMPONENTS[arch]},
                       delta_common_bus_W={k: arm_bus_W[k] - hall_only_bus_W[k] for k in COMMON_NON_DISCHARGE},
                       interstage_loss_bus_W=interstage_loss_bus_W, extra_ppu_bus_W=extra_ppu_bus_W)


def overhead_from_boundary_ledgers(arm_ledger: Mapping, hall_only_ledger: Mapping) -> BusOverhead:
    """Build a v1-conformant overhead from two ledgers in the bus_power_boundary_v1 output format
    ({'boundary_version', 'architecture', 'items': [{'component', 'P_bus_W', ...}], ...}); read by structure, the
    boundary module is not imported. Both ledgers must describe the same operating mode (the caller's duty)."""
    parsed = {}
    for name, led in (("arm_ledger", arm_ledger), ("hall_only_ledger", hall_only_ledger)):
        if not isinstance(led, Mapping) or "items" not in led:
            raise BreakevenInputError(f"{name} must be a bus_power_boundary_v1 ledger mapping with 'items'")
        if led.get("boundary_version") != BOUNDARY_VERSION:
            raise BreakevenInputError(f"{name}.boundary_version = {led.get('boundary_version')!r}, "
                                      f"expected {BOUNDARY_VERSION!r}")
        comps = [it.get("component") for it in led["items"]]
        if len(set(comps)) != len(comps):
            raise BreakevenInputError(f"{name}: duplicate components {comps}")
        parsed[name] = (led.get("architecture"), {it["component"]: it.get("P_bus_W") for it in led["items"]})
    arch, arm = parsed["arm_ledger"]
    h_arch, hall = parsed["hall_only_ledger"]
    if h_arch != "hall_only":
        raise BreakevenInputError(f"hall_only_ledger.architecture = {h_arch!r}, expected 'hall_only'")
    return overhead_from_ledgers(arch, arm, hall, 0.0, 0.0)


def check_boundary_contract() -> dict:
    """Lazily resolve abep_sim/arch_boundary.py and check version and component names against this module's copy of
    the shared contract. Not needed by the relations in this module; raises BreakevenContractError if absent."""
    try:
        mod = importlib.import_module("abep_sim.arch_boundary")
    except ImportError as exc:
        raise BreakevenContractError(
            "abep_sim/arch_boundary.py (bus_power_boundary_v1) is not present in this checkout; it is built by the "
            "bus-power-boundary lane. breakeven.py uses only its component names and does not import it.") from exc
    version = getattr(mod, "BOUNDARY_VERSION", None)
    if version != BOUNDARY_VERSION:
        raise BreakevenContractError(f"abep_sim.arch_boundary.BOUNDARY_VERSION = {version!r}, expected {BOUNDARY_VERSION!r}")
    common = getattr(mod, "COMMON_COMPONENTS", None)
    if common is not None and tuple(common) != COMMON_COMPONENTS:
        raise BreakevenContractError(f"arch_boundary.COMMON_COMPONENTS {tuple(common)} != {COMMON_COMPONENTS}")
    pre = getattr(mod, "PREIONIZER_COMPONENTS", None)
    if pre is not None:
        for arch, comps in SOURCE_COMPONENTS.items():
            if tuple(pre.get(arch, ())) != comps:
                raise BreakevenContractError(f"arch_boundary.PREIONIZER_COMPONENTS[{arch!r}] = {pre.get(arch)!r}, "
                                             f"expected {comps}")
    return {"module": mod.__name__, "BOUNDARY_VERSION": version, "components_checked": common is not None}


# ----------------------------------------------------------------------------------------------------------------------
# Hall-only state and arm state
def hall_only_state(ref: HallReference) -> dict:
    """Identities of the efficiency decomposition at the Hall-only point (no physics closure involved)."""
    mix = ref.mix
    I_b = ref.eta_u * ref.mdot_kg_s * mix.coulomb_per_kg
    I_d = I_b / ref.eta_b
    P_d = ref.V_d_V * I_d
    T = ref.gamma_div * math.sqrt(ref.eta_v * ref.V_d_V) * mix.thrust_coefficient * I_b
    eta_a = ref.gamma_div ** 2 * ref.eta_v * ref.eta_b * ref.eta_u * mix.charge_factor
    return {"I_b_A": I_b, "I_d_A": I_d, "I_e_A": I_d - I_b, "P_d_W": P_d, "P_d_bus_W": P_d / ref.eta_ppu_discharge,
            "T_N": T, "P_jet_W": T * T / (2.0 * ref.mdot_kg_s), "eta_a": eta_a,
            "eta_a_check": T * T / (2.0 * ref.mdot_kg_s * P_d),
            "Pi_H_bus_W_per_A": ref.V_d_V / (ref.eta_b * ref.eta_ppu_discharge),
            "overhead_per_beam_A_W_per_A": ref.V_d_V * (1.0 / ref.eta_b - ref.eta_v)}


def delta_s_max(ref: HallReference, resp: PreionResponse) -> float:
    """Largest delivered-ion mass share: Hall-born share stays >= 0 and total utilization <= 1."""
    caps = []
    if resp.alpha < 1.0:
        caps.append(ref.eta_u / (1.0 - resp.alpha))
    if resp.alpha > 0.0:
        caps.append((1.0 - ref.eta_u) / resp.alpha)
    return min(caps)


def _check_delta(ref: HallReference, resp: PreionResponse, delta_s: float) -> float:
    d = _num("delta_s", delta_s, lo=0.0)
    cap = delta_s_max(ref, resp)
    if d > cap * (1.0 + 1e-12):
        raise BreakevenInputError(f"delta_s = {d} exceeds its physical cap {cap} (Hall-born share >= 0, eta_u <= 1)")
    return min(d, cap)


def _dimensionless(ref: HallReference, resp: PreionResponse) -> tuple:
    """(n1, d1): N and D normalised by the Hall-only per-share values; N ~ eta_u0 + n1 d, D ~ eta_u0 + d1 d."""
    mH, mS = ref.mix, resp.mix_delivered
    inv_eta_bS = 1.0 + (1.0 - resp.chi) * (1.0 / ref.eta_b - 1.0)
    R_T = math.sqrt(resp.eta_v_delivered / ref.eta_v) * mS.velocity_coefficient / mH.velocity_coefficient
    R_P = (mS.coulomb_per_kg / mH.coulomb_per_kg) * ref.eta_b * inv_eta_bS
    return R_T - (1.0 - resp.alpha), R_P - (1.0 - resp.alpha), R_T, R_P


def arm_state(ref: HallReference, resp: PreionResponse, delta_s: float) -> dict:
    """Arm composition at delivered-ion mass share delta_s (V_d-independent quantities only)."""
    d = _check_delta(ref, resp, delta_s)
    mH, mS = ref.mix, resp.mix_delivered
    u_H = max(ref.eta_u - (1.0 - resp.alpha) * d, 0.0)
    inv_eta_bS = 1.0 + (1.0 - resp.chi) * (1.0 / ref.eta_b - 1.0)
    N = math.sqrt(ref.eta_v) * mH.velocity_coefficient * u_H + math.sqrt(resp.eta_v_delivered) * mS.velocity_coefficient * d
    D = mH.coulomb_per_kg * u_H / ref.eta_b + mS.coulomb_per_kg * d * inv_eta_bS
    eta_a = ref.gamma_div ** 2 * N * N / (2.0 * D)
    return {"delta_s": d, "u_H": u_H, "eta_u": u_H + d, "delta_eta_u": u_H + d - ref.eta_u, "N": N, "D": D,
            "eta_a": eta_a, "I_H_per_mdot": mH.coulomb_per_kg * u_H, "I_S_per_mdot": mS.coulomb_per_kg * d,
            "eta_b_delivered": 1.0 / inv_eta_bS}


def efficiency_ratio(ref: HallReference, resp: PreionResponse, delta_s: float) -> float:
    """R = eta_a(arm) / eta_a(hall_only) (common discharge converter, so also the bus-referred ratio)."""
    return arm_state(ref, resp, delta_s)["eta_a"] / hall_only_state(ref)["eta_a"]


# ----------------------------------------------------------------------------------------------------------------------
# (1) Power break-even at the bus, both conventions evaluated independently
def evaluate_arm(ref: HallReference, resp: PreionResponse, overhead: BusOverhead, delta_s: float) -> dict:
    """Evaluate the arm against hall_only at delivered-ion share delta_s under both comparison conventions."""
    if not isinstance(overhead, BusOverhead):
        raise BreakevenInputError("overhead must be a BusOverhead")
    h = hall_only_state(ref)
    a = arm_state(ref, resp, delta_s)
    O = overhead.total_W
    P0b = h["P_d_bus_W"]
    omega = O / P0b
    g, md = ref.gamma_div, ref.mdot_kg_s
    # equal thrust: V_d chosen so that T_arm = T_0
    V_T = (h["T_N"] / (g * md * a["N"])) ** 2
    P_T = V_T * md * a["D"]
    P_Tb = P_T / ref.eta_ppu_discharge
    saving = P0b - P_Tb - O
    eq_T = {"V_d_V": V_T, "V_d_ratio": V_T / ref.V_d_V, "P_d_bus_W": P_Tb, "net_bus_saving_W": saving,
            "net_bus_saving_fraction": saving / P0b, "breaks_even": saving >= 0.0,
            "ledger_arm_W": {"hall_discharge": P_Tb, **overhead.ledger_lines()},
            "ledger_hall_only_W": {"hall_discharge": P0b}}
    eq_T["ledger_residual_W"] = (P0b - sum(eq_T["ledger_arm_W"].values())) - saving
    eq_T["eta_a_residual"] = h["T_N"] ** 2 / (2.0 * md * P_T) - a["eta_a"]      # energy identity T^2 = 2 mdot eta_a P_d
    # equal bus power: the Hall discharge gets what the overhead leaves
    P_Pb = P0b - O
    if P_Pb <= 0.0:
        eq_P = {"feasible": False, "reason": "overhead >= Hall-only discharge bus power (omega >= 1)",
                "breaks_even": False}
    else:
        P_P = P_Pb * ref.eta_ppu_discharge
        V_P = P_P / (md * a["D"])
        T_P = g * math.sqrt(V_P) * md * a["N"]
        eq_P = {"feasible": True, "V_d_V": V_P, "V_d_ratio": V_P / ref.V_d_V, "P_d_bus_W": P_Pb, "T_N": T_P,
                "thrust_gain_fraction": T_P / h["T_N"] - 1.0, "breaks_even": T_P >= h["T_N"],
                "ledger_arm_W": {"hall_discharge": P_Pb, **overhead.ledger_lines()},
                "ledger_hall_only_W": {"hall_discharge": P0b}}
        eq_P["ledger_residual_W"] = sum(eq_P["ledger_arm_W"].values()) - P0b
        eq_P["eta_a_residual"] = T_P ** 2 / (2.0 * md * P_P) - a["eta_a"]
    R = a["eta_a"] / h["eta_a"]
    return {"arch": overhead.arch, "overhead_W": O, "boundary_v1_conformant": overhead.boundary_v1_conformant,
            "omega": omega, "R": R,
            "R_required": (1.0 / (1.0 - omega)) if omega < 1.0 else math.inf,
            "master_breaks_even": omega < 1.0 and R * (1.0 - omega) >= 1.0,
            "hall_only": h, "arm": a, "equal_thrust": eq_T, "equal_bus_power": eq_P}


# ----------------------------------------------------------------------------------------------------------------------
# (2) Required utilization gain (closed form; both conventions share one break-even locus)
def required_utilization_gain(ref: HallReference, resp: PreionResponse, overhead: BusOverhead) -> dict:
    """Smallest delivered-ion share delta_s* (and delta_eta_u* = alpha delta_s*) at which the arm breaks even.

    Break-even <=> q(d) = (1-omega)(eta_u0 + n1 d)^2 - eta_u0 (eta_u0 + d1 d) >= 0 (both conventions). With omega < 1
    q is convex with q(0) = -omega eta_u0^2 <= 0, so the break-even set is [d*, delta_s_max] (empty if d* > cap).
    Independent of eta_transport (which only links produced to delivered ions)."""
    if not isinstance(overhead, BusOverhead):
        raise BreakevenInputError("overhead must be a BusOverhead")
    h = hall_only_state(ref)
    O = overhead.total_W
    P0b = h["P_d_bus_W"]
    omega = O / P0b
    cap = delta_s_max(ref, resp)
    n1, d1, R_T, R_P = _dimensionless(ref, resp)
    out = {"arch": overhead.arch, "overhead_W": O, "boundary_v1_conformant": overhead.boundary_v1_conformant,
           "P_d_bus0_W": P0b, "omega": omega, "delta_s_max": cap,
           "n1": n1, "d1": d1, "R_T": R_T, "R_P": R_P, "alpha": resp.alpha}
    if omega <= 0.0:     # a non-positive overhead breaks even without any delivered ion
        out.update(status="OK" if omega == 0.0 else "OK_NONPOSITIVE_OVERHEAD", delta_s_star=0.0,
                   delta_eta_u_star=0.0, eta_u_at_breakeven=ref.eta_u, V_d_ratio_at_breakeven=1.0)
        return out
    if omega >= 1.0:
        out.update(status="INFEASIBLE_OVERHEAD_GE_DISCHARGE", delta_s_star=None, delta_eta_u_star=None)
        return out
    u0 = ref.eta_u
    a = (1.0 - omega) * n1 * n1
    b = 2.0 * (1.0 - omega) * u0 * n1 - u0 * d1
    c = -omega * u0 * u0
    disc = b * b - 4.0 * a * c
    den = b + math.sqrt(disc)
    if den <= 0.0:
        out.update(status="INFEASIBLE_NO_GAIN", delta_s_star=None, delta_eta_u_star=None)
        return out
    d_star = -2.0 * c / den
    if d_star > cap * (1.0 + 1e-12):
        out.update(status="INFEASIBLE_UTILIZATION_CAP", delta_s_star=d_star, delta_eta_u_star=resp.alpha * d_star)
        return out
    d_star = min(d_star, cap)
    st = arm_state(ref, resp, d_star)
    out.update(status="OK" if resp.alpha > 0.0 else "OK_SUBSTITUTION_ONLY", delta_s_star=d_star,
               delta_eta_u_star=resp.alpha * d_star, eta_u_at_breakeven=st["eta_u"],
               V_d_ratio_at_breakeven=(math.sqrt(ref.eta_v) * ref.mix.velocity_coefficient * u0 / st["N"]) ** 2)
    return out


def required_utilization_gain_add_only_closed_form(eta_u0: float, omega: float) -> float:
    """Add-only, same mix, eta_v_S = eta_v: delta_eta_u* = eta_u0 omega / (1 - omega) (omega in [0, 1))."""
    u0 = _num("eta_u0", eta_u0, lo=0.0, hi=1.0, lo_open=True)
    w = _num("omega", omega, lo=0.0, hi=1.0, hi_open=True)
    return u0 * w / (1.0 - w)


# ----------------------------------------------------------------------------------------------------------------------
# (3) Break-even ion production cost of the source
def breakeven_delivered_cost(ref: HallReference, resp: PreionResponse, delta_s: float, fixed_overhead_W: float) -> float:
    """Largest bus power per ampere of S ions delivered into the Hall beam [W/A] at which the arm still breaks even
    at share delta_s, given fixed (non-ion-scaling) bus overhead. May be negative (no source cost pays)."""
    d = _check_delta(ref, resp, delta_s)
    if d <= 0.0:
        raise BreakevenInputError("delta_s must be > 0 (use marginal_breakeven_delivered_cost for the limit)")
    Of = _num("fixed_overhead_W", fixed_overhead_W, lo=0.0)
    h = hall_only_state(ref)
    R = efficiency_ratio(ref, resp, d)
    I_S = d * ref.mdot_kg_s * resp.mix_delivered.coulomb_per_kg
    return (h["P_d_bus_W"] * (1.0 - 1.0 / R) - Of) / I_S


def marginal_breakeven_delivered_cost(ref: HallReference, resp: PreionResponse) -> float:
    """Limit delta_s -> 0 with no fixed overhead: Pi_H (rho_H/rho_S) (2 R_T - R_P - (1 - alpha)) [W/A]."""
    h = hall_only_state(ref)
    _, _, R_T, R_P = _dimensionless(ref, resp)
    return h["Pi_H_bus_W_per_A"] * (ref.mix.coulomb_per_kg / resp.mix_delivered.coulomb_per_kg) * (
        2.0 * R_T - R_P - (1.0 - resp.alpha))


def supremum_breakeven_delivered_cost(ref: HallReference, resp: PreionResponse, fixed_overhead_W: float,
                                      n_grid: int) -> dict:
    """sup over delta_s in (0, cap] of breakeven_delivered_cost (grid + golden-section refinement). With zero fixed
    overhead the delta_s -> 0 limit is included as a candidate (attained only in the limit)."""
    Of = _num("fixed_overhead_W", fixed_overhead_W, lo=0.0)
    if isinstance(n_grid, bool) or not isinstance(n_grid, int) or n_grid < 16:
        raise BreakevenInputError("n_grid must be an integer >= 16")
    cap = delta_s_max(ref, resp)
    # geometric + linear grid over (0, cap]
    pts = sorted({cap * 10.0 ** (-6.0 + 6.0 * i / (n_grid - 1)) for i in range(n_grid)}
                 | {cap * (i + 1) / n_grid for i in range(n_grid)})
    vals = [breakeven_delivered_cost(ref, resp, p, Of) for p in pts]
    k = max(range(len(pts)), key=lambda i: vals[i])
    lo, hi = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
    f = lambda x: breakeven_delivered_cost(ref, resp, x, Of)
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    x1, x2 = hi - gr * (hi - lo), lo + gr * (hi - lo)
    f1, f2 = f(x1), f(x2)
    for _ in range(80):
        if f1 < f2:
            lo, x1, f1 = x1, x2, f2
            x2 = lo + gr * (hi - lo)
            f2 = f(x2)
        else:
            hi, x2, f2 = x2, x1, f1
            x1 = hi - gr * (hi - lo)
            f1 = f(x1)
    best_d, best = (x1, f1) if f1 >= vals[k] else (pts[k], vals[k])
    out = {"sup_W_per_A": best, "argmax_delta_s": best_d, "attained_in_limit": False, "fixed_overhead_W": Of}
    if Of == 0.0:
        m = marginal_breakeven_delivered_cost(ref, resp)
        if m >= best:
            out.update(sup_W_per_A=m, argmax_delta_s=0.0, attained_in_limit=True)
    return out


def bus_referred_source_cost(published_cost: float, unit: str, power_reference: str, chain: Mapping[str, float],
                             mean_charge_per_ion: float) -> float:
    """Convert a published ion production cost to bus W per A of source ions (same ion-count basis as published).

    unit 'eV_per_ion' is divided by the mean charge per ion (W/A = eV/ion / <Z>); power_reference 'absorbed' (power
    absorbed by the plasma, as in G&K Eqs. 4.5-7 / 4.6-27) needs chain {'coupling', 'generator'}; 'forward' needs
    {'generator'}; 'bus' needs {}. Every stage efficiency is explicit."""
    c = _num("published_cost", published_cost, lo=0.0, lo_open=True)
    if unit not in COST_UNITS:
        raise BreakevenInputError(f"unit {unit!r} not in {COST_UNITS}")
    if power_reference not in POWER_REFERENCES:
        raise BreakevenInputError(f"power_reference {power_reference!r} not in {tuple(POWER_REFERENCES)}")
    _keys("chain", chain, POWER_REFERENCES[power_reference])
    z = _num("mean_charge_per_ion", mean_charge_per_ion, lo=1.0)
    if unit == "eV_per_ion":
        c = c / z
    for k in POWER_REFERENCES[power_reference]:
        c /= _num(f"chain[{k}]", chain[k], lo=0.0, hi=1.0, lo_open=True)
    return c


def achievable_delivered_share(ref: HallReference, resp: PreionResponse, generator_bus_W: float,
                               source_cost_bus_W_per_A: float, eta_transport: float) -> dict:
    """What a source of given bus cost buys: delta_s = eta_t P_gen / (C_src mdot rho_S), delta_eta_u = alpha delta_s.

    The supply side of the break-even: compare with required_utilization_gain (which does not depend on eta_t).
    Raises if the implied share exceeds the physical cap (the Hall cannot accept that many delivered ions)."""
    P = _num("generator_bus_W", generator_bus_W, lo=0.0)
    C = _num("source_cost_bus_W_per_A", source_cost_bus_W_per_A, lo=0.0, lo_open=True)
    et = _num("eta_transport", eta_transport, lo=0.0, hi=1.0)
    I_src = P / C
    I_S = et * I_src
    d = I_S / (ref.mdot_kg_s * resp.mix_delivered.coulomb_per_kg)
    cap = delta_s_max(ref, resp)
    if d > cap * (1.0 + 1e-12):
        raise BreakevenInputError(f"implied delivered share {d} exceeds the physical cap {cap}: the source would "
                                  "deliver more ions than the Hall flow can carry at these inputs")
    return {"I_source_A": I_src, "I_delivered_A": I_S, "delta_s": d, "delta_eta_u": resp.alpha * d,
            "delivered_cost_W_per_A": (C / et) if et > 0.0 else math.inf}


def place_evidence(ref: HallReference, resp: PreionResponse, fixed_overhead_W: float, source_cost_bus: Evidenced,
                   eta_transport: Evidenced, n_grid: int) -> dict:
    """Place a source's bus-referred production cost [W/A] and its transport efficiency (same ion basis) against the
    break-even surface of one Hall reference point. Returns the payable delivered-share interval, if any."""
    C = _ev("source_cost_bus", source_cost_bus, "W/A").value
    _num("source_cost_bus.value", C, lo=0.0, lo_open=True)
    et = _ev("eta_transport", eta_transport, "1").value
    _num("eta_transport.value", et, lo=0.0, hi=1.0, lo_open=True)
    Of = _num("fixed_overhead_W", fixed_overhead_W, lo=0.0)
    C_del = C / et
    sup = supremum_breakeven_delivered_cost(ref, resp, Of, n_grid)
    res = {"source_cost_bus_W_per_A": C, "eta_transport": et, "delivered_cost_W_per_A": C_del,
           "sup_breakeven_delivered_cost_W_per_A": sup["sup_W_per_A"],
           "margin_ratio": sup["sup_W_per_A"] / C_del,
           "eta_transport_min": (C / sup["sup_W_per_A"]) if sup["sup_W_per_A"] > 0.0 else math.inf,
           "evidence": {"source_cost": [source_cost_bus.evidence_class, source_cost_bus.source],
                        "eta_transport": [eta_transport.evidence_class, eta_transport.source],
                        "result": "model-derived (breakeven_v1; conditional on the declared assumptions)"}}
    if C_del > sup["sup_W_per_A"]:
        res.update(status="CANNOT_BREAK_EVEN_IN_MODEL_FAMILY", payable_delta_s=None)
        return res
    cap = delta_s_max(ref, resp)
    g = lambda d: breakeven_delivered_cost(ref, resp, d, Of) - C_del
    pts = [cap * (i + 1) / n_grid for i in range(n_grid)]
    pts = sorted(set(pts) | {cap * 10.0 ** (-6.0 + 6.0 * i / (n_grid - 1)) for i in range(n_grid)})
    ok = [g(p) >= 0.0 for p in pts]
    if not any(ok):     # only the delta_s -> 0 limit pays: no finite gain is payable
        res.update(status="BREAKS_EVEN_ONLY_IN_LIMIT", payable_delta_s=None)
        return res

    def edge(i_in, i_out):
        a_, b_ = pts[i_in], pts[i_out]
        for _ in range(100):
            m = 0.5 * (a_ + b_)
            a_, b_ = (m, b_) if g(m) >= 0.0 else (a_, m)
        return a_
    first = ok.index(True)
    last = len(ok) - 1 - ok[::-1].index(True)
    if first == 0:       # pays down to the smallest grid share; with no fixed overhead it pays in the limit d -> 0
        lo = 0.0 if Of == 0.0 else pts[0]
    else:
        lo = edge(first, first - 1)
    hi = pts[last] if last == len(pts) - 1 else edge(last, last + 1)
    res.update(status="BREAK_EVEN_POSSIBLE", payable_delta_s=[lo, hi],
               payable_delta_eta_u=[resp.alpha * lo, resp.alpha * hi],
               source_bus_power_at_payable_W=[C_del * x * ref.mdot_kg_s * resp.mix_delivered.coulomb_per_kg
                                              for x in (lo, hi)],
               non_contiguous=not all(ok[first:last + 1]))
    return res


# ----------------------------------------------------------------------------------------------------------------------
# (4) Mass break-even
def mass_breakeven(arch: str, convention: str, benefit: Evidenced, mass_sensitivity: Evidenced,
                   propellant_mass_change: Evidenced, added_hardware_kg: Mapping[str, Evidenced]) -> dict:
    """dm_benefit > m_source + m_PPU + m_magnets (+ interstage, added thermal).

    equal_thrust: benefit = net bus-power saving [W], mass_sensitivity = power-system specific mass [kg/W].
    equal_bus_power: benefit = thrust gain [N], mass_sensitivity = system mass equivalent of thrust [kg/N].
    propellant_mass_change: stored-propellant change [kg] (negative = saving). Hardware keys: HARDWARE_KEYS."""
    if arch not in PREIONIZED_ARCHITECTURES:
        raise BreakevenInputError(f"arch {arch!r} not in {PREIONIZED_ARCHITECTURES}")
    if convention not in CONVENTIONS:
        raise BreakevenInputError(f"convention {convention!r} not in {CONVENTIONS}")
    b_unit, s_unit = ("W", "kg/W") if convention == "equal_thrust" else ("N", "kg/N")
    b = _ev("benefit", benefit, b_unit).value
    s = _ev("mass_sensitivity", mass_sensitivity, s_unit).value
    _num("mass_sensitivity.value", s, lo=0.0)
    dm_prop = _ev("propellant_mass_change", propellant_mass_change, "kg").value
    _keys("added_hardware_kg", added_hardware_kg, HARDWARE_KEYS)
    hw = {k: _ev(f"added_hardware_kg[{k}]", v, "kg").value for k, v in added_hardware_kg.items()}
    for k, v in hw.items():
        _num(f"added_hardware_kg[{k}]", v, lo=0.0)
    m_hw = sum(hw.values())
    m_benefit = s * b - dm_prop
    return {"arch": arch, "convention": convention, "benefit_mass_kg": m_benefit, "hardware_mass_kg": m_hw,
            "net_mass_benefit_kg": m_benefit - m_hw, "breaks_even": m_benefit - m_hw >= 0.0,
            "required_benefit": ((m_hw + dm_prop) / s) if s > 0.0 else math.inf, "required_benefit_unit": b_unit,
            "hardware_kg": hw}


# ----------------------------------------------------------------------------------------------------------------------
# (5) Life break-even
def hall_erosion_life_ratio(ion_flux_ref: float, sputter_yield_ref: float, ion_flux_arm: float,
                            sputter_yield_arm: float) -> float:
    """L_arm / L_ref at one wall location and material: erosion rate ~ J_i Y(eps_i) (G&K Eq. 7.5-1)."""
    J0 = _num("ion_flux_ref", ion_flux_ref, lo=0.0, lo_open=True)
    Y0 = _num("sputter_yield_ref", sputter_yield_ref, lo=0.0, lo_open=True)
    J1 = _num("ion_flux_arm", ion_flux_arm, lo=0.0, lo_open=True)
    Y1 = _num("sputter_yield_arm", sputter_yield_arm, lo=0.0, lo_open=True)
    return (J0 * Y0) / (J1 * Y1)


def life_breakeven(required_firing: Evidenced, qualification_factor: Evidenced,
                   hall_only_limits: Mapping[str, Evidenced], arm_limits: Mapping[str, Evidenced],
                   source_mechanisms: Sequence[str]) -> dict:
    """Series-system life inequalities. Life break-even: min(arm limits) >= min(hall_only limits). Requirement:
    min(limits) >= qualification_factor * required_firing. arm_limits must hold every hall_only mechanism (common
    hardware, possibly at a different stress) plus the listed source mechanisms."""
    t_req = _ev("required_firing", required_firing, "h").value
    _num("required_firing.value", t_req, lo=0.0, lo_open=True)
    k_q = _ev("qualification_factor", qualification_factor, "1").value
    _num("qualification_factor.value", k_q, lo=1.0)
    if not isinstance(hall_only_limits, Mapping) or not hall_only_limits:
        raise BreakevenInputError("hall_only_limits must be a non-empty mapping mechanism -> Evidenced hours")
    src = list(source_mechanisms)
    if not src:
        raise BreakevenInputError("source_mechanisms must name at least one source life limit")
    overlap = [m for m in src if m in hall_only_limits]
    if overlap:
        raise BreakevenInputError(f"source mechanisms {overlap} also appear in hall_only_limits")
    _keys("arm_limits", arm_limits, list(hall_only_limits) + src)
    L0 = {k: _ev(f"hall_only_limits[{k}]", v, "h").value for k, v in hall_only_limits.items()}
    L1 = {k: _ev(f"arm_limits[{k}]", v, "h").value for k, v in arm_limits.items()}
    for d in (L0, L1):
        for k, v in d.items():
            _num(f"life[{k}]", v, lo=0.0, lo_open=True)
    life0, life1 = min(L0.values()), min(L1.values())
    common1 = min(L1[k] for k in L0)
    src1 = min(L1[k] for k in src)
    need = k_q * t_req
    return {"life_hall_only_h": life0, "life_arm_h": life1,
            "limiting_hall_only": sorted(k for k, v in L0.items() if v == life0),
            "limiting_arm": sorted(k for k, v in L1.items() if v == life1),
            "common_hardware_life_change_h": {k: L1[k] - L0[k] for k in L0},
            "source_limited": src1 < common1, "life_breaks_even": life1 >= life0,
            "required_life_h": need, "requirement_met_hall_only": life0 >= need, "requirement_met_arm": life1 >= need,
            "classification": ("ARM_NOT_WORSE" if life1 >= life0 else
                               "ARM_WORSE_SOURCE_LIMITED" if src1 < common1 else "ARM_WORSE_COMMON_HARDWARE")}
