"""Reduced standalone RF propulsion model (parallel RF || Hall investigation, v2).

Chain:  P_DC (bus) -> P_net,feed (antenna/coupler feed terminal) -> P_absorbed -> plasma state -> magnetic nozzle -> T

STATUS: model-derived, UNVALIDATED_REDUCED_RF_MODEL, never score-bearing. It generates hypotheses, operating grids
and experiment plans; it cannot by itself declare an architecture viable (spec sec. 14).

Reuse (read-only):
* ``plasma_chem.solve_global`` - the species-resolved 0-D global model (unverified Arrhenius-class chemistry; CLAUDE.md
  next-work item 6 says the N2 fit was ~3x off and the N fit ~2x low; the HallThruster.jl tables are NOT wired into it).
* ``plasma_chem.Chamber`` - constructed here with every field explicit (its dataclass defaults are never used).
* The polytropic ion-energy relation of ``archengine.magnetic_nozzle`` (reference only; not validated).

Magnetic nozzle (model-derived preliminary relation):
    E_i = T_e [ 1/2 + gamma/(gamma-1) (1 - R_m^(1-gamma)) ]
Energy bound (enforced; a violation is MODEL_ERROR, never clipped):
    P_kin = I_exit * E_i  <=  P_kin,max = P_absorbed - P_ionization/excitation - P_dissociation - P_wall
where P_wall (ion + electron wall losses of the global model) is the unavoidable loss of this reduced model. At the
global model's own balance P_kin,max equals its exit-electron energy flux (2 T_e per exiting electron), so with
the bound reduces analytically to E_i <= 2 T_e, i.e. R_m <= R_m* = [1 - 1.5 (gamma-1)/gamma]^(-1/(gamma-1))
(4.214 at gamma = 1.2; 4.33 at 1.1, 4.05 at 1.4, 3.95 at 5/3), independent of chamber and flow. Beyond R_m* the
polytropic relation asks for more ion energy than the source model supplies - an inconsistency of the reduced model
that the bound exposes instead of hiding. Thrust bound (directed-flow): T <= sqrt(2 mdot_i P_kin,max).

Every coefficient is an explicit input (a Quantity with evidence, or a named reference model). There are no
numerical defaults for coupling efficiency, detachment, divergence, gamma or R_m.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import E_CHARGE, G0, K_B
from .parallel_contracts import (ContractError, FeedState, Quantity, Status, TBD, real, value_of)
from .plasma_chem import M_ION, M_NEUT, Chamber, solve_global

MODEL_ID = "rf_reduced_v1"
VALIDATION_STATUS = "UNVALIDATED_REDUCED_RF_MODEL"
EVIDENCE_CLASS = "model-derived"

UNRESOLVED_PHYSICS = (
    "RF antenna impedance closure",
    "S11 / reflected power (only if supplied as evidence)",
    "high-fidelity wave-plasma coupling",
    "plasma detachment",
    "magnetic-nozzle kinetic effects",
    "non-Maxwellian EEDF",
    "detailed plume interaction",
    "atomic-oxygen material lifetime",
    "long-duration wall/antenna erosion",
    "global-model chemistry: unverified Arrhenius-class rates (N2 fit ~3x off; N ~2x low; tables not unified)",
    "exit ion Bohm energy is not in the global model's power balance",
)

REFERENCE_DETACHMENT = "archengine_v1_eta_det"      # eta_det = max(1 - 0.9/sqrt(R_m), 0)  (unvalidated reference)
REFERENCE_DIVERGENCE = "archengine_v1_divergence"   # div = 45 deg / (1 + 0.05 R_m)       (unvalidated reference)
_ARCH_REF = "abep_sim/archengine.py::magnetic_nozzle (exploratory reference relation; not validated)"


@dataclass(frozen=True)
class RFChamberSpec:
    """Discharge chamber of the standalone RF thruster. Every field a Quantity (geometry is design input)."""
    volume_m3: Quantity
    wall_area_m2: Quantity
    exit_area_m2: Quantity
    T_gas_K: Quantity
    h_l: Quantity
    magnetised_wall_factor: Quantity
    exit_neutral_clausing: Quantity
    geometry_id: str

    def chamber(self) -> Chamber:
        return Chamber(volume_m3=value_of(self.volume_m3, "volume_m3", "m^3"),
                       wall_area_m2=value_of(self.wall_area_m2, "wall_area_m2", "m^2"),
                       exit_area_m2=value_of(self.exit_area_m2, "exit_area_m2", "m^2"),
                       T_gas_K=value_of(self.T_gas_K, "T_gas_K", "K"),
                       h_l=value_of(self.h_l, "h_l", "1"),
                       magnetised_wall_factor=value_of(self.magnetised_wall_factor, "magnetised_wall_factor", "1"),
                       exit_neutral_K=value_of(self.exit_neutral_clausing, "exit_neutral_clausing", "1"))


@dataclass(frozen=True)
class RFCoupling:
    """Power chain. ``eta_bus_to_feed`` = P_net,feed / P_DC (generator + matching + filters + harness, net of
    reflection); ``eta_antenna`` = P_absorbed / P_net,feed (coil ohmic + coupling). ``eta_generator`` and
    ``P_reflected_W`` are optional evidence (TBD when unknown; never invented, never zero by default)."""
    frequency_Hz: Quantity
    eta_bus_to_feed: Quantity
    eta_antenna: Quantity
    eta_generator: object          # Quantity | TBD
    P_reflected_W: object          # Quantity | TBD
    antenna_geometry_id: str


@dataclass(frozen=True)
class RFNozzleSpec:
    """Magnetic nozzle. ``detachment`` / ``divergence``: a Quantity or the named unvalidated reference model."""
    gamma: Quantity
    R_m: Quantity
    B0_T: Quantity
    magnetic_geometry_id: str
    topology_source: str
    detachment: object             # Quantity (fraction) | REFERENCE_DETACHMENT
    divergence: object             # Quantity (deg)      | REFERENCE_DIVERGENCE


def _eta_det(spec: RFNozzleSpec, R_m: float):
    if spec.detachment == REFERENCE_DETACHMENT:
        return max(1 - 0.9 / math.sqrt(R_m), 0.0), {"model": REFERENCE_DETACHMENT, "source": _ARCH_REF}
    e = value_of(spec.detachment, "detachment efficiency", "1")
    if not 0.0 <= e <= 1.0:
        raise ContractError(f"detachment efficiency must be in [0, 1], got {e!r}")
    return e, spec.detachment.to_dict()


def _divergence(spec: RFNozzleSpec, R_m: float):
    if spec.divergence == REFERENCE_DIVERGENCE:
        return 45.0 / (1 + 0.05 * R_m), {"model": REFERENCE_DIVERGENCE, "source": _ARCH_REF}
    d = value_of(spec.divergence, "plume divergence", "deg")
    if not 0.0 <= d < 90.0:
        raise ContractError(f"plume divergence half-angle must be in [0, 90) deg, got {d!r}")
    return d, spec.divergence.to_dict()


def _tbd(name, requires):
    return TBD(name, requires)


def R_m_star(gamma: float) -> float:
    """Analytic expansion-ratio limit of the polytropic relation under the global model's exit budget (E_i <= 2 T_e)."""
    g = real(gamma, "gamma")
    if g <= 1.0:
        raise ContractError("gamma must be > 1")
    base = 1 - 1.5 * (g - 1) / g
    return math.inf if base <= 0 else base ** (-1 / (g - 1))


def run(feed: FeedState, P_dc_W: float, chamber: RFChamberSpec, coupling: RFCoupling, nozzle: RFNozzleSpec,
        P_magnet_W: Quantity, Te_bounds=(0.5, 150.0)) -> dict:
    """Evaluate the reduced RF chain at one operating point. Returns a dict of outputs (sec. 10) with
    evidence_class model-derived, validation_status UNVALIDATED_REDUCED_RF_MODEL, score_bearing False."""
    if not isinstance(feed, FeedState):
        raise ContractError("feed must be a FeedState")
    P_dc = real(P_dc_W, "P_dc_W")
    if P_dc < 0:
        raise ContractError("P_dc_W must be >= 0")
    eta_feed = value_of(coupling.eta_bus_to_feed, "eta_bus_to_feed", "1")
    eta_ant = value_of(coupling.eta_antenna, "eta_antenna", "1")
    for n, e in (("eta_bus_to_feed", eta_feed), ("eta_antenna", eta_ant)):
        if not 0.0 < e <= 1.0:
            raise ContractError(f"{n} must be in (0, 1], got {e!r}")
    P_net = P_dc * eta_feed
    P_abs = P_net * eta_ant
    if isinstance(coupling.eta_generator, Quantity):
        eg = value_of(coupling.eta_generator, "eta_generator", "1")
        if not 0.0 < eg <= 1.0:
            raise ContractError(f"eta_generator must be in (0, 1], got {eg!r}")
    if isinstance(coupling.eta_generator, Quantity) and isinstance(coupling.P_reflected_W, Quantity):
        P_fwd = P_dc * value_of(coupling.eta_generator, "eta_generator", "1")
        P_refl = value_of(coupling.P_reflected_W, "P_reflected_W", "W")
        if P_fwd - P_refl < P_net * (1 - 1e-12):
            raise ContractError("P_forward - P_reflected is below the net feed power: the supplied generator, "
                                "reflection and bus-to-feed evidence are inconsistent")
    else:
        P_fwd = _tbd("P_forward_W", "generator efficiency evidence (eta_generator)") \
            if not isinstance(coupling.eta_generator, Quantity) else P_dc * coupling.eta_generator.value
        P_refl = _tbd("P_reflected_W", "measured S11 / reflected power at the operating point")
    P_mag = value_of(P_magnet_W, "rf magnet load", "W")
    gamma = value_of(nozzle.gamma, "polytropic gamma", "1")
    R_m = value_of(nozzle.R_m, "expansion ratio R_m", "1")
    B0 = value_of(nozzle.B0_T, "B0", "T")
    if gamma <= 1.0 or R_m < 1.0:
        raise ContractError("gamma must be > 1 and R_m >= 1")

    ch = chamber.chamber()
    # the routed feed's pressure/temperature are not used: the chamber gas temperature is the chamber spec's T_gas_K
    unmapped = [s for s, m in feed.species_mdot_kg_s().items() if m > 0 and s not in M_NEUT]
    if unmapped:
        raise ContractError(f"species {unmapped} are not represented in plasma_chem (M_NEUT)")
    inflow = {s: m for s, m in feed.species_mdot_kg_s().items() if s in M_NEUT}
    base = {
        "model_id": MODEL_ID, "evidence_class": EVIDENCE_CLASS, "validation_status": VALIDATION_STATUS,
        "score_bearing": False, "unresolved_physics": list(UNRESOLVED_PHYSICS),
        "P_dc_W": P_dc, "P_net_feed_W": P_net, "P_forward_W": P_fwd, "P_reflected_W": P_refl,
        "P_absorbed_W": P_abs, "source_loss_W": P_dc - P_abs, "magnet_power_W": P_mag,
        "frequency_Hz": value_of(coupling.frequency_Hz, "frequency", "Hz"), "B0_T": B0, "gamma": gamma, "R_m": R_m,
        "antenna_geometry_id": coupling.antenna_geometry_id, "magnetic_geometry_id": nozzle.magnetic_geometry_id,
        "chamber_geometry_id": chamber.geometry_id, "magnetic_topology_source": nozzle.topology_source,
        "mdot_in_kg_s": feed.mdot_total_kg_s,
    }
    if feed.mdot_total_kg_s <= 0.0 or P_abs <= 0.0:
        return {**base, "model_status": Status.NOT_SUSTAINED.value, "reason": "no propellant or no absorbed power",
                "thrust_N": 0.0}
    try:
        st = solve_global(ch, inflow, P_abs, f_cutoff_Hz=base["frequency_Hz"], Te_bounds=Te_bounds)
    except (ArithmeticError, ValueError) as exc:
        return {**base, "model_status": Status.NUMERICAL_FAILURE.value, "reason": f"solve_global raised {exc!r}"}
    if st.branch == "none":
        why = ("absorbed power exceeds the most power the model plasma can dissipate at this flow (burnout region)"
               if P_abs > st.P_max_dissipable_W else
               "global model finds no sustained discharge (no particle-balance root inside Te bounds)")
        return {**base, "model_status": Status.NOT_SUSTAINED.value, "Te_eV": st.Te_eV, "reason": why,
                "P_max_dissipable_W": st.P_max_dissipable_W, "thrust_N": 0.0}
    if not st.sustained:
        return {**base, "model_status": Status.NUMERICAL_FAILURE.value, "Te_eV": st.Te_eV,
                "reason": "Te pinned at a bound or utilisation > 1 (unphysical solve)"}

    # power partition and energy bound
    P_iz, P_diss = st.power["ionisation_excitation_W"], st.power["dissociation_W"]
    P_wall, P_exit_e = st.power["wall_W"], st.power["electron_exit_W"]
    energy_residual = P_abs - (P_iz + P_diss + P_wall + P_exit_e)
    P_kin_max = P_abs - P_iz - P_diss - P_wall
    I_exit = sum(st.ion_exit_A.values())
    E_i = st.Te_eV * (0.5 + gamma / (gamma - 1) * (1 - R_m ** (1 - gamma)))
    P_kin = I_exit * E_i                                 # [W]: (I/e) ions/s x e E_i J
    mdot_i = sum(st.ion_exit_A[i] / E_CHARGE * M_ION[i] for i in st.ion_exit_A)
    eta_det, det_ev = _eta_det(nozzle, R_m)
    div, div_ev = _divergence(nozzle, R_m)
    cos_div = 0.5 * (1 + math.cos(math.radians(div)))
    T_raw = sum((st.ion_exit_A[i] / E_CHARGE) * M_ION[i] * math.sqrt(2 * E_CHARGE * E_i / M_ION[i])
                for i in st.ion_exit_A)
    T = T_raw * eta_det * cos_div
    P_jet = (T * T / (2 * mdot_i)) if mdot_i > 0 else 0.0     # directed jet power consistent with the reported T
    T_bound = math.sqrt(2 * mdot_i * max(P_kin_max, 0.0)) * eta_det * cos_div

    # neutral effusion and mass balance (same conductance as solve_global)
    cbar = {s: math.sqrt(8 * K_B * ch.T_gas_K / (math.pi * M_NEUT[s])) for s in M_NEUT}
    C_x = {s: ch.exit_neutral_K * ch.exit_area_m2 * cbar[s] / 4.0 for s in M_NEUT}
    m_neut_out = sum(st.n_neut.get(s, 0.0) * C_x[s] * M_NEUT[s] for s in M_NEUT)
    m_ion_out = mdot_i
    mass_residual = feed.mdot_total_kg_s - (m_neut_out + m_ion_out)

    out = {**base,
           "Te_eV": st.Te_eV, "ne_m3": st.n_e, "neutral_species_m3": dict(st.n_neut), "ion_species_m3": dict(st.n_ion),
           "ion_currents_A": dict(st.ion_exit_A), "ion_wall_current_A": st.ion_wall_A,
           "utilization": st.util_total, "utilization_by_species": dict(st.util),
           "power_partition_W": {"ionization_excitation": P_iz, "dissociation": P_diss, "wall": P_wall,
                                 "electron_exit": P_exit_e},
           "P_kinetic_W": P_kin, "P_kinetic_max_W": P_kin_max, "E_i_eV": E_i,
           "magnetic_nozzle_efficiency": (P_jet / P_abs) if P_abs > 0 else 0.0,   # T^2/(2 mdot_i) / P_abs
           "detachment_efficiency": eta_det, "detachment_evidence": det_ev,
           "plume_divergence_deg": div, "divergence_evidence": div_ev,
           "thrust_bound_N": T_bound,
           "mdot_ion_kg_s": m_ion_out, "mdot_neutral_out_kg_s": m_neut_out,
           "mass_balance_residual": mass_residual / feed.mdot_total_kg_s,
           "energy_balance_residual": energy_residual / P_abs}
    tol_E = max(1e-9 * P_kin_max, 10.0 * abs(energy_residual))   # relative to the bound itself, not to P_abs
    if P_kin > P_kin_max + tol_E or T > T_bound * (1 + 1e-9) + 1e-15:
        return {**out, "model_status": Status.MODEL_ERROR.value, "thrust_N": TBD("thrust_N", "reduced model "
                "violated its energy bound; result withheld"),
                "reason": (f"polytropic ion energy {E_i:.3g} eV x I_exit {I_exit:.3g} A = {P_kin:.4g} W exceeds the "
                           f"kinetic power available {P_kin_max:.4g} W (P_abs - P_iz - P_diss - P_wall)")}
    Isp = T / (feed.mdot_total_kg_s * G0)
    out.update(model_status=Status.PASS.value, thrust_N=T, Isp_s=Isp, P_jet_W=P_jet,
               T_per_Pabsorbed_N_W=T / P_abs)
    return out


# ------------------------------------------------------------------ high-fidelity RF coupling interface (sec. 12)

@dataclass(frozen=True)
class RFCouplingRecord:
    """Interface for future high-fidelity RF electromagnetic data (EM solver or measurement), NOT a solver.
    Such records enter v2 only through the immutable-export -> sha256 -> schema -> registry -> admission pattern
    (see rf_registry). Unknown quantities stay TBD; nothing is defaulted."""
    frequency_Hz: float
    antenna_geometry_id: str
    magnetic_geometry_id: str
    P_dc_W: float
    P_forward_W: object
    P_reflected_W: object
    S11: object                        # complex reflection coefficient magnitude/phase record, or TBD
    P_absorbed_W: object
    antenna_loss_W: object
    matching_loss_W: object
    plasma_impedance_ohm: object       # (R, X) or TBD
    source: str
    evidence_class: str

    def __post_init__(self):
        from .parallel_contracts import evidence_class as _ev, nonempty as _ne
        real(self.frequency_Hz, "frequency_Hz")
        if real(self.P_dc_W, "P_dc_W") < 0:
            raise ContractError("P_dc_W must be >= 0")
        _ne(self.antenna_geometry_id, "antenna_geometry_id")
        _ne(self.magnetic_geometry_id, "magnetic_geometry_id")
        _ne(self.source, "source")
        _ev(self.evidence_class, "evidence_class")
        known = [getattr(self, k) for k in ("P_forward_W", "P_reflected_W", "P_absorbed_W", "antenna_loss_W",
                                            "matching_loss_W")]
        for v in known:
            if not isinstance(v, TBD):
                if real(v, "power") < 0:
                    raise ContractError("coupling powers must be >= 0")
        if not any(isinstance(getattr(self, k), TBD) for k in ("P_forward_W", "P_reflected_W", "P_absorbed_W",
                                                               "antenna_loss_W")):
            if self.P_forward_W - self.P_reflected_W < self.P_absorbed_W + self.antenna_loss_W - 1e-9:
                raise ContractError("P_forward - P_reflected < P_absorbed + antenna loss: record violates energy")
