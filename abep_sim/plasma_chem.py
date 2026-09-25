"""Species-resolved global (0-D) plasma model with energy balance (Phase 3, items 9, 10, 11, 16).

Species: neutrals O, O2, N2, N ; ions O+, O2+, N2+, N+ ; electrons (Maxwellian, T_e in eV).
Processes (rate coefficients k(T_e) in m^3/s, literature-class Arrhenius fits anchored at ~10 eV):
  ionisation           e + X -> X+ + 2e
  dissociation         e + O2 -> O + O + e ;  e + N2 -> N + N + e
  dissociative ionis.  e + O2 -> O + O+ + 2e
  excitation + vibr.   lumped into collisional energy loss per ionisation eps_c(T_e) = a + b / T_e  (Lieberman-style)
  wall loss            Bohm flux u_B = sqrt(e T_e / m_i) through effective area A_eff = h_l A_wall + A_exit
  charge exchange      handled downstream in the Hall/plume model (needs beam velocity)

Balance (steady state, Lieberman & Lichtenberg ch. 10):
  particle:  sum_i n_e n_g,j k_iz,j->i V  = sum_i n_i u_B,i A_eff          -> fixes T_e for given neutral mix
  power:     P_abs = e V sum_i R_iz,i eps_c,i + e (Gamma_wall (eps_i,w + 2 T_e) + Gamma_exit (2 T_e))
             -> fixes n_e for given P_abs
  neutrals:  inflow_j = outflow_j (effusion through A_exit) + consumption (ionisation, dissociation)
Outputs: T_e, n_e, ion composition, ion current leaving through A_exit (usable), wall ion loss,
utilisation per species, energy cost per usable ion, power partition, dissociation fraction of O2/N2.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from .constants import E_CHARGE, K_B, M_SPECIES, AMU

ME = 9.10938e-31
M_ION = {"O+": 16 * AMU, "O2+": 32 * AMU, "N2+": 28 * AMU, "N+": 14 * AMU, "Xe+": 131.3 * AMU}
M_NEUT = {"O": 16 * AMU, "O2": 32 * AMU, "N2": 28 * AMU, "N": 14 * AMU, "Xe": 131.3 * AMU}

# k = k0 * Te^p * exp(-E/Te)   [m^3/s]; anchored: N2 iz(10 eV)≈3e-15, O2 iz≈2.5e-15, O iz≈3e-15, N iz≈3e-15
RATES = {
    ("N2", "iz"):   (4.5e-15, 0.5, 15.6, "N2+"),
    ("O2", "iz"):   (3.8e-15, 0.5, 12.1, "O2+"),
    ("O", "iz"):    (3.9e-15, 0.5, 13.6, "O+"),
    ("N", "iz"):    (4.2e-15, 0.5, 14.5, "N+"),
    ("Xe", "iz"):   (1.6e-14, 0.5, 12.13, "Xe+"),
    ("O2", "diz"):  (1.5e-15, 0.5, 20.3, "O+"),      # dissociative ionisation -> O + O+
    ("O2", "diss"): (6.9e-15, 0.0, 6.3, None),       # -> 2 O   (Gudmundsson-class)
    ("N2", "diss"): (3.0e-15, 0.5, 11.0, None),      # -> 2 N   (via predissociating states)
}
# collisional energy loss per ionisation event eps_c(Te) ≈ a + b/Te  [eV]  (includes excitation + vibrational)
EPS_C = {"N2": (25.0, 375.0), "O2": (22.0, 190.0), "O": (15.0, 125.0), "N": (15.0, 125.0), "Xe": (18.0, 90.0)}
E_DISS = {"O2": 5.12, "N2": 9.76}


RATE_TABLES: dict = {}          # (species, proc) -> (eps array, k array) from cross-section-derived tables
CHEM_PROVENANCE = {}


def _load_rate_tables():
    import os, numpy as np
    d = os.path.join(os.path.dirname(__file__), "data", "rates")
    files = {("N2", "iz"): "ionization_N2_N2+.dat"}
    for key, fn in files.items():
        p = os.path.join(d, fn)
        if os.path.exists(p):
            arr = np.loadtxt(p, skiprows=2)
            RATE_TABLES[key] = (arr[:, 0], arr[:, 1])
            CHEM_PROVENANCE[key] = f"table:{fn} (Itikawa 2006 via HallThruster.jl v0.23.1)"


def k_rate(species, proc, Te):
    """Rate coefficient [m^3/s] at electron temperature Te [eV]. Cross-section-derived tables (Maxwellian, tabulated
    against mean electron energy 3/2 Te) are authoritative where present; otherwise the literature-class fit."""
    tab = RATE_TABLES.get((species, proc))
    if tab is not None:
        import numpy as np
        return float(np.interp(1.5 * Te, tab[0], tab[1]))
    k0, p, E, _ = RATES[(species, proc)]
    return k0 * Te ** p * math.exp(-E / max(Te, 0.05))


_load_rate_tables()


def eps_c(species, Te):
    a, b = EPS_C[species]
    return a + b / max(Te, 0.05)


@dataclass
class Chamber:
    volume_m3: float = 3.0e-4
    wall_area_m2: float = 0.03
    exit_area_m2: float = 3.0e-3
    T_gas_K: float = 500.0
    h_l: float = 0.4               # edge-to-centre density ratio for wall flux (magnetised: lower)
    magnetised_wall_factor: float = 1.0   # <1 reduces cross-field wall loss (ECR/RF with axial B)
    exit_neutral_K: float = 0.7    # Clausing factor for neutral effusion through the exit


@dataclass
class PlasmaState:
    Te_eV: float
    n_e: float
    n_ion: dict
    n_neut: dict
    ion_exit_A: dict               # ion current per species leaving through exit [A]
    ion_wall_A: float
    util: dict                     # usable ion mass flow / neutral inflow mass, per parent species
    util_total: float
    eV_per_usable_ion: float
    power: dict
    diss_frac: dict
    P_abs_W: float
    overdense_ratio: float = 0.0
    sustained: bool = True          # False: particle balance has no root inside Te_bounds (Te pinned) — no valid plasma
    branch: str = "ionisation"      # "ionisation" | "burnout" (util > 0.9) | "none"
    P_max_dissipable_W: float = 0.0 # most power a Maxwellian plasma can dissipate in this chamber within Te_bounds


def solve_global(ch: Chamber, inflow_kgps: dict, P_abs_W: float, f_cutoff_Hz: float | None = None,
                 Te_bounds=(0.5, 150.0)) -> PlasmaState:
    """inflow_kgps: neutral mass inflow per species {"O":..,"O2":..,"N2":..}. Returns steady state."""
    V, A_w, A_x = ch.volume_m3, ch.wall_area_m2, ch.exit_area_m2
    A_eff = ch.h_l * ch.magnetised_wall_factor * A_w + A_x
    cbar = {s: math.sqrt(8 * K_B * ch.T_gas_K / (math.pi * M_NEUT[s])) for s in M_NEUT}
    C_x = {s: ch.exit_neutral_K * A_x * cbar[s] / 4.0 for s in M_NEUT}     # neutral exit conductance [m^3/s]
    nin = {s: inflow_kgps.get(s, 0.0) / M_NEUT[s] for s in M_NEUT}          # molecules/s in

    # ions reaching walls recombine and return to the neutral pool; only exit-plane ions leave the chamber as ions
    f_exit = A_x / A_eff

    def neutral_densities(Te, ne):
        """Neutral balance with dissociation producing atoms. The system is triangular (molecules first, then atoms
        from their dissociation), so it is solved exactly in one pass. Ionisation removes a neutral permanently only
        for the exit fraction of ions; wall-lost ions recombine (O+ -> O, N2+ -> N2, ...) and stay in the balance."""
        n = {}
        for mol in ("O2", "N2"):
            k_iz = k_rate(mol, "iz", Te) * f_exit
            k_diz = (k_rate(mol, "diz", Te) if (mol, "diz") in RATES else 0.0) * f_exit
            n[mol] = nin[mol] / (C_x[mol] + ne * V * (k_iz + k_diz + k_rate(mol, "diss", Te)))
        # O: inflow + 2 per O2 dissociation + 1 per dissociative ionisation (O2 -> O + O+, exit part; the wall part
        # recombines to O2 and was never removed above)
        src_O = nin["O"] + ne * V * n["O2"] * (2 * k_rate("O2", "diss", Te) + k_rate("O2", "diz", Te) * f_exit)
        n["O"] = src_O / (C_x["O"] + ne * V * k_rate("O", "iz", Te) * f_exit)
        src_N = nin["N"] + ne * V * n["N2"] * 2 * k_rate("N2", "diss", Te)
        n["N"] = src_N / (C_x["N"] + ne * V * k_rate("N", "iz", Te) * f_exit)
        n["Xe"] = nin["Xe"] / (C_x["Xe"] + ne * V * k_rate("Xe", "iz", Te) * f_exit)
        return n

    def ion_sources(Te, n):
        """Ion production rate per m^3 per unit ne, by ion species."""
        S = {i: 0.0 for i in M_ION}
        S["N2+"] += k_rate("N2", "iz", Te) * n["N2"]
        S["O2+"] += k_rate("O2", "iz", Te) * n["O2"]
        S["O+"] += k_rate("O", "iz", Te) * n["O"] + k_rate("O2", "diz", Te) * n["O2"]
        S["N+"] += k_rate("N", "iz", Te) * n["N"]
        S["Xe+"] += k_rate("Xe", "iz", Te) * n.get("Xe", 0.0)
        return S

    def particle_residual(Te, ne):
        n = neutral_densities(Te, ne)
        S = ion_sources(Te, n)
        tot_src = sum(S.values())
        if tot_src <= 0:
            return -1.0, n, S
        # steady state per species: n_i u_B,i A_eff = S_i V  ->  n_i ∝ S_i / u_B,i (light ions leave faster);
        # with sum n_i = ne the total loss per unit ne is  A_eff/V * sum S / sum(S/u_B)
        uB = {i: math.sqrt(E_CHARGE * Te / M_ION[i]) for i in S}
        loss = (tot_src / sum(S[i] / uB[i] for i in S)) * A_eff / V
        return tot_src - loss, n, S

    # iterate: guess ne, solve Te by bisection on particle balance, then ne from power balance; repeat
    def solve_ne(Te_):
        """Particle balance at fixed Te: r(ne)/ne = V S(ne,Te)/ne - u_B A_eff decreases monotonically in ne (ionisation
        saturates at the recycling-limited supply), so ne(Te) is unique; NaN below the ionisation threshold."""
        lo, hi = 1e10, 1e21
        if particle_residual(Te_, lo)[0] <= 0:
            return float("nan")
        if particle_residual(Te_, hi)[0] > 0:
            return hi
        for _ in range(48):
            mid = math.sqrt(lo * hi)
            if particle_residual(Te_, mid)[0] > 0: lo = mid
            else: hi = mid
        return math.sqrt(lo * hi)

    def P_of_Te(Te_):
        ne_ = solve_ne(Te_)
        if ne_ != ne_:
            return float("nan"), ne_
        _, n_, S_ = particle_residual(Te_, ne_)
        tot = sum(S_.values())
        uB_ = {i: math.sqrt(E_CHARGE * Te_ / M_ION[i]) for i in S_}
        ws = sum(S_[i] / uB_[i] for i in S_) if tot > 0 else 0.0
        fr = {i: (S_[i] / uB_[i]) / ws for i in S_} if ws > 0 else {i: 0.25 for i in S_}
        cost_ = (eps_c("N2", Te_) * k_rate("N2", "iz", Te_) * n_["N2"] + eps_c("O2", Te_) * (k_rate("O2", "iz", Te_) + k_rate("O2", "diz", Te_)) * n_["O2"]
                 + eps_c("O", Te_) * k_rate("O", "iz", Te_) * n_["O"] + eps_c("N", Te_) * k_rate("N", "iz", Te_) * n_["N"]
                 + eps_c("Xe", Te_) * k_rate("Xe", "iz", Te_) * n_["Xe"]
                 + E_DISS["O2"] * k_rate("O2", "diss", Te_) * n_["O2"] + E_DISS["N2"] * k_rate("N2", "diss", Te_) * n_["N2"]) * V
        uBm = sum(fr[i] * uB_[i] for i in fr)
        Gw = uBm * ch.h_l * ch.magnetised_wall_factor * A_w; Gx = uBm * A_x
        return E_CHARGE * ne_ * (cost_ + Gw * (5.2 * Te_ + 2 * Te_) + Gx * (2 * Te_)), ne_

    # Parameterise by Te (the natural variable): find the lowest Te where the dissipated power equals the absorbed power.
    Te_scan = [Te_bounds[0] * (Te_bounds[1] / Te_bounds[0]) ** (k / 44.0) for k in range(45)]
    Pv = [P_of_Te(T)[0] for T in Te_scan]
    converged = False; Te = Te_bounds[1]; ne = 1e13
    # the ionisation threshold: just above it ne(Te) rises steeply from zero, so low powers live between an invalid
    # (NaN) scan point and the first valid one — locate the threshold and treat P(Te_th) = 0
    for k in range(len(Te_scan) - 1):
        if Pv[k] != Pv[k] and Pv[k + 1] == Pv[k + 1]:
            lo, hi = Te_scan[k], Te_scan[k + 1]
            for _ in range(50):
                mid = math.sqrt(lo * hi)
                if P_of_Te(mid)[0] == P_of_Te(mid)[0]: hi = mid
                else: lo = mid
            Te_scan.insert(k + 1, hi); Pv.insert(k + 1, 0.0)
            break
    for k in range(len(Te_scan) - 1):
        a, b = Pv[k], Pv[k + 1]
        if a == a and b == b and a <= P_abs_W < b:
            lo, hi = Te_scan[k], Te_scan[k + 1]
            for _ in range(40):
                mid = math.sqrt(lo * hi)
                pm = P_of_Te(mid)[0]
                if pm != pm or pm < P_abs_W: lo = mid
                else: hi = mid
            Te = hi; ne = solve_ne(Te); converged = ne == ne
            break
    P_max_diss = max((v for v in Pv if v == v), default=0.0)

    def solve_Te(ne_):
        return Te
    if not converged:
        ne = solve_ne(Te) if solve_ne(Te) == solve_ne(Te) else 1e13
    _, n, S = particle_residual(Te, ne)
    tot_src = sum(S.values())
    uBi = {i: math.sqrt(E_CHARGE * Te / M_ION[i]) for i in S}
    wsum = sum(S[i] / uBi[i] for i in S)
    frac = {i: (S[i] / uBi[i]) / wsum for i in S}                 # density fractions: n_i ∝ S_i / u_B,i
    n_ion = {i: ne * frac[i] for i in S}
    ion_exit = {i: E_CHARGE * n_ion[i] * math.sqrt(E_CHARGE * Te / M_ION[i]) * A_x for i in S}
    ion_wall = sum(E_CHARGE * n_ion[i] * math.sqrt(E_CHARGE * Te / M_ION[i]) for i in S) * ch.h_l * ch.magnetised_wall_factor * A_w
    # utilisation: usable ion mass leaving / neutral mass in, mapped to parent neutral species
    mass_out = {i: ion_exit[i] / E_CHARGE * M_ION[i] for i in S}
    m_in_tot = sum(inflow_kgps.values())
    util_total = sum(mass_out.values()) / m_in_tot if m_in_tot > 0 else 0.0
    util = {"O": (mass_out["O+"]) / max(inflow_kgps.get("O", 0) + inflow_kgps.get("O2", 0), 1e-30),
            "N2": (mass_out["N2+"] + mass_out["N+"]) / max(inflow_kgps.get("N2", 0), 1e-30),
            "O2": mass_out["O2+"] / max(inflow_kgps.get("O2", 0), 1e-30),
            "Xe": mass_out["Xe+"] / max(inflow_kgps.get("Xe", 0), 1e-30)}
    I_usable = sum(ion_exit.values())
    P_iz = E_CHARGE * ne * (eps_c("N2", Te) * k_rate("N2", "iz", Te) * n["N2"] + eps_c("O2", Te) * (k_rate("O2", "iz", Te) + k_rate("O2", "diz", Te)) * n["O2"]
                            + eps_c("O", Te) * k_rate("O", "iz", Te) * n["O"] + eps_c("N", Te) * k_rate("N", "iz", Te) * n["N"]
                            + eps_c("Xe", Te) * k_rate("Xe", "iz", Te) * n["Xe"]) * V
    P_diss = E_CHARGE * ne * (E_DISS["O2"] * k_rate("O2", "diss", Te) * n["O2"] + E_DISS["N2"] * k_rate("N2", "diss", Te) * n["N2"]) * V
    P_wall = ion_wall * (5.2 * Te + 2 * Te)
    P_exit_e = I_usable * 2 * Te
    diss = {"O2": 1.0 - n["O2"] * C_x["O2"] / max(nin["O2"], 1e-30) - (mass_out["O2+"] / M_NEUT["O2"]) / max(nin["O2"], 1e-30),
            "N2": 1.0 - n["N2"] * C_x["N2"] / max(nin["N2"], 1e-30) - (mass_out["N2+"] / M_NEUT["N2"]) / max(nin["N2"], 1e-30)}
    over = 0.0
    if f_cutoff_Hz:
        n_c = ME * 8.854e-12 * (2 * math.pi * f_cutoff_Hz) ** 2 / E_CHARGE ** 2
        over = ne / n_c
    pinned = (Te > 0.98 * Te_bounds[1]) or (Te < 1.02 * Te_bounds[0]) or util_total > 1.0 + 1e-3 or not converged
    branch = "burnout" if (converged and util_total > 0.9) else ("ionisation" if converged else "none")
    return PlasmaState(Te, ne, n_ion, n, ion_exit, ion_wall, util, util_total,
                       (P_abs_W / (I_usable / E_CHARGE) / E_CHARGE) if I_usable > 0 else float("inf"),
                       {"ionisation_excitation_W": P_iz, "dissociation_W": P_diss, "wall_W": P_wall, "electron_exit_W": P_exit_e},
                       diss, P_abs_W, over, not pinned, branch, P_max_diss)
