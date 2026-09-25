"""STATUS: independent reduced-order SANITY model only (not a production Hall solver). The authoritative Hall solver is
HallThruster.jl (see hallthruster_bridge/PINNED.toml); this fixed-point formulation can collapse to the no-discharge
attractor and is kept for conservation/trend cross-checks.

Quasi-1-D steady-state Hall thruster discharge (stabilisation gate 3 — structural upgrade of the 0-D model).

Axial coordinate z: anode at 0, channel exit at L, cathode plane at L + L_plume. Cross-section A(z) = channel annulus.
Unknowns on the grid: neutral densities n_N2(z), n_N(z); ion densities/velocities for N2+ and N+; electron temperature
T_e(z); potential phi(z); discharge current I_d.

  neutrals   u_n dn_s/dz = - n_e n_s (k_iz,s + k_diss,s) + (dissociation source for N) + (wall-recombined ions)
  ions       cold, collisionless, ballistic: an ion born at z' with the neutral speed reaches z with
             u = sqrt(u_n^2 + 2e(phi(z') - phi(z))/m_i); radial wall loss inside the channel (Bohm flux to walls)
             attenuates each birth-cohort as exp(-int nu_w/u dz); n_i(z) = sum_z' S(z') dz' * surv / u(z', z)
  electrons  quasineutral n_e = sum n_i; current conservation e A (Gamma_i - Gamma_e) = I_d;
             Ohm: Gamma_e = -mu_perp (n_e E + d(n_e T_e)/dz)  [T_e in V];  mu_perp = mu_classical + mu_anomalous,
             mu_classical = (e/m nu)/(1+Omega^2), mu_anomalous = alpha_B(z) / (16 B);  alpha_B = 1/10 inside, 1 outside
             (i.e. Bohm coefficient 1/160 inside the channel, 1/16 in the plume — the standard two-zone closure);
             I_d fixed by  integral E dz = V_d - V_cathode_coupling.
  energy     (5/2) d(Gamma_e T_e)/dz = Gamma_e E - n_e sum n_s k_s eps_c,s - wall loss (inside channel)
             marched from the cathode plane (T_e = T_cathode) toward the anode (electrons flow -z).
Thrust = sum over species of ion mass flux x exit velocity at the plume end x divergence factor; P_d = I_d V_d.
Nothing here is fitted to the ABEP operating point; the transport coefficients are the standard literature values.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from .constants import E_CHARGE, K_B, AMU
from .plasma_chem import k_rate, eps_c, E_DISS
from .materials import DB

ME = 9.10938e-31
M = {"N2": 28.014 * AMU, "N": 14.007 * AMU}
ION = {"N2": "N2+", "N": "N+"}


@dataclass
class Hall1DGeometry:
    r_in_m: float
    r_out_m: float
    L_m: float
    B_max_T: float
    B_sigma_in_m: float | None = None      # Gaussian width of B inside the channel (default: channel width)
    B_sigma_out_m: float | None = None     # width outside (default: channel width)
    L_plume_m: float = 0.03
    wall: str = "BN"
    alpha_in: float = 0.1                  # Bohm coefficient inside = alpha_in/16  (1/160)
    alpha_out: float = 1.0                 # outside = 1/16
    T_cathode_eV: float = 3.0
    V_cc: float = 20.0                     # cathode coupling voltage
    T_gas_K: float = 600.0
    h_wall: float = 0.3                    # edge-to-centre density ratio for radial ion loss
    div_deg: float = 25.0

    @property
    def width(self):
        return self.r_out_m - self.r_in_m

    @property
    def area(self):
        return math.pi * (self.r_out_m ** 2 - self.r_in_m ** 2)


def solve_hall1d(g: Hall1DGeometry, Vd: float, mdot_kgps: float, N: int = 160, iters: int = 400, relax: float = 0.15,
                 tol: float = 1e-5, verbose: bool = False) -> dict:
    z_end = g.L_m + g.L_plume_m
    z = np.linspace(0.0, z_end, N); dz = z[1] - z[0]
    inside = z <= g.L_m
    A = g.area; w = g.width
    s_in = g.B_sigma_in_m or w; s_out = g.B_sigma_out_m or w
    B = np.where(z <= g.L_m, g.B_max_T * np.exp(-((z - g.L_m) / s_in) ** 2), g.B_max_T * np.exp(-((z - g.L_m) / s_out) ** 2))
    B = np.maximum(B, 0.02 * g.B_max_T)
    alpha = np.where(inside, g.alpha_in, g.alpha_out)
    u_n = {s: math.sqrt(8 * K_B * g.T_gas_K / (math.pi * M[s])) / 4.0 * 2.0 for s in M}   # directed ~ c_bar/2
    Gamma_in = mdot_kgps / M["N2"] / A                                                    # N2 flux at the anode [1/m2/s]
    # initial guesses
    phi = Vd * (1 - 1 / (1 + np.exp(-(z - g.L_m) / (0.3 * w))))                            # drop near the exit
    Te = 5.0 + 20.0 * np.exp(-((z - g.L_m) / w) ** 2)
    ne = np.full(N, 1e17)
    Id = 0.5 * mdot_kgps / M["N2"] * E_CHARGE
    wall_mat = DB[g.wall]
    hist = []
    for it in range(iters):
        # ---------------- neutrals (march from anode) with the current ne, Te
        nN2 = np.zeros(N); nN = np.zeros(N)
        GN2 = Gamma_in; GN = 0.0
        S = {"N2": np.zeros(N), "N": np.zeros(N)}
        for j in range(N):
            nN2[j] = GN2 / u_n["N2"]; nN[j] = GN / u_n["N"]
            kiz2 = k_rate("N2", "iz", Te[j]); kd2 = k_rate("N2", "diss", Te[j]); kizN = k_rate("N", "iz", Te[j])
            S["N2"][j] = ne[j] * nN2[j] * kiz2; S["N"][j] = ne[j] * nN[j] * kizN
            dGN2 = -ne[j] * nN2[j] * (kiz2 + kd2) * dz
            dGN = (2 * ne[j] * nN2[j] * kd2 - ne[j] * nN[j] * kizN) * dz
            GN2 = max(GN2 + dGN2, 0.0); GN = max(GN + dGN, 0.0)
        # ---------------- ions: ballistic from birth location, radial wall loss inside the channel
        ni = {}; Gi = {}; ui_exit = {}
        dphi = phi[:, None] - phi[None, :]                          # phi(z') - phi(z), rows = birth z'
        for sp in ("N2", "N"):
            m = M[sp]
            u = np.sqrt(np.maximum(u_n[sp] ** 2 + 2 * E_CHARGE * np.maximum(dphi, 0.0) / m, u_n[sp] ** 2))
            ahead = (z[None, :] >= z[:, None])
            uB = np.sqrt(E_CHARGE * np.maximum(Te, 0.5) / m)
            nu_w = np.where(inside, 2 * g.h_wall * uB / w, 0.0)      # radial loss frequency
            # survival from z' to z: exp(-sum nu_w dz / u) along the path (use cumulative integral of nu_w/u_local)
            loss_rate = nu_w[None, :] / u                              # per metre, evaluated at z for cohort z'
            cum = np.cumsum(np.where(ahead, loss_rate, 0.0) * dz, axis=1)
            surv = np.where(ahead, np.exp(-cum), 0.0)
            src = S[sp] * dz                                           # ions/m2/s born per cell
            ni[sp] = (src[:, None] * surv / u).sum(axis=0)
            Gi[sp] = (src[:, None] * surv).sum(axis=0)
            ui_exit[sp] = u[:, -1]
            ni[sp + "_wall"] = (src[:, None] * surv * np.where(ahead, loss_rate, 0.0) * dz).sum(axis=0)  # wall-lost ions per cell
        ne_new = np.maximum(ni["N2"] + ni["N"], 1e13)
        Gi_tot = Gi["N2"] + Gi["N"]
        # ---------------- electrons: mobility, Ohm's law, current closure
        nn = nN2 + nN
        nu_m = nn * 2.5e-13 + 1e5
        Om = E_CHARGE * B / (ME * nu_m)
        mu = (E_CHARGE / (ME * nu_m)) / (1 + Om ** 2) + alpha / (16.0 * B)
        pe_grad = np.gradient(ne_new * Te, dz)
        # Gamma_e = Gamma_i - Id/(eA)  (electrons flow toward the anode: Gamma_e < 0)
        # E = -Gamma_e/(mu ne) - (1/ne) d(ne Te)/dz  = a*Id + b
        a = (1.0 / (E_CHARGE * A)) / (mu * ne_new)
        b = -Gi_tot / (mu * ne_new) - pe_grad / ne_new
        Vint = Vd - g.V_cc
        Id_new = (Vint - np.sum(b) * dz) / (np.sum(a) * dz)
        Id_new = max(Id_new, E_CHARGE * A * Gi_tot[-1] * 1.02)       # at least the beam current
        E = a * Id_new + b
        phi_new = Vd - np.concatenate([[0.0], np.cumsum(0.5 * (E[1:] + E[:-1]) * dz)])
        Ge = Gi_tot - Id_new / (E_CHARGE * A)                          # negative
        # ---------------- electron energy: march from the cathode plane toward the anode
        Te_new = np.empty(N); Te_new[-1] = g.T_cathode_eV
        Gabs = np.abs(Ge)
        for j in range(N - 1, 0, -1):
            T = Te_new[j]
            heat = Gabs[j] * E[j]                                      # e-flux x field, W/m3 / e
            inel = ne_new[j] * (nN2[j] * (k_rate("N2", "iz", T) * eps_c("N2", T) + k_rate("N2", "diss", T) * E_DISS["N2"])
                                + nN[j] * k_rate("N", "iz", T) * eps_c("N", T))
            wall = 0.0
            if inside[j]:
                uBj = math.sqrt(E_CHARGE * max(T, 0.5) / (22 * AMU))
                delta = min(wall_mat.see_yield(2 * T), 0.99)
                phis = 1.02 * T if delta >= 0.983 else T * math.log((1 - delta) * math.sqrt(22 * AMU / (2 * math.pi * ME)))
                wall = ne_new[j] * 2 * g.h_wall * uBj / w * (2 * T + phis)
            dT = (heat - inel - wall) / (2.5 * max(Gabs[j], 1e10)) * dz     # going toward the anode (-z)
            Te_new[j - 1] = min(max(T + dT, 0.5), 0.5 * Vd)
        # ---------------- relax and check
        dn = np.max(np.abs(np.log(ne_new) - np.log(ne)))
        ne = np.exp((1 - relax) * np.log(ne) + relax * np.log(ne_new))
        Te = (1 - relax) * Te + relax * Te_new
        phi = (1 - relax) * phi + relax * phi_new
        Id = (1 - relax) * Id + relax * Id_new
        hist.append(Id)
        if verbose and it % 50 == 0:
            print(it, f"Id={Id:.3f} dn={dn:.2e} Te_max={Te.max():.1f} ne_max={ne.max():.2e}")
        if it > 50 and dn < tol and abs(hist[-1] / hist[-2] - 1) < tol:
            break
    # ---------------- performance
    cos_div = 0.5 * (1 + math.cos(math.radians(g.div_deg)))
    T_N = 0.0; I_b = 0.0; mdot_i = 0.0
    for sp in ("N2", "N"):
        m = M[sp]
        # birth cohorts reaching the plume end with survival
        u = np.sqrt(np.maximum(u_n[sp] ** 2 + 2 * E_CHARGE * np.maximum(phi - phi[-1], 0.0) / m, u_n[sp] ** 2))
        uB = np.sqrt(E_CHARGE * np.maximum(Te, 0.5) / m)
        nu_w = np.where(inside, 2 * g.h_wall * uB / w, 0.0)
        # survival along path using the local final-velocity approximation
        S_sp = (S["N2"] if sp == "N2" else S["N"]) * dz
        # recompute exact survival cohort-wise
        dphi = phi[:, None] - phi[None, :]
        uu = np.sqrt(np.maximum(u_n[sp] ** 2 + 2 * E_CHARGE * np.maximum(dphi, 0.0) / m, u_n[sp] ** 2))
        ahead = (z[None, :] >= z[:, None])
        cum = np.cumsum(np.where(ahead, nu_w[None, :] / uu, 0.0) * dz, axis=1)
        surv_end = np.exp(-cum[:, -1])
        flux = S_sp * surv_end                                          # ions/m2/s reaching the end, per birth cell
        T_N += np.sum(flux * m * u) * A * cos_div
        I_b += np.sum(flux) * A * E_CHARGE
        mdot_i += np.sum(flux) * A * m
    P = Id * Vd
    return {"T_N": T_N, "I_d_A": Id, "I_b_A": I_b, "P_d_W": P, "eta_b": I_b / Id if Id > 0 else 0.0,
            "util": mdot_i / mdot_kgps, "Isp_s": T_N / (9.80665 * mdot_kgps), "eta_anode": T_N ** 2 / (2 * mdot_kgps * P) if P > 0 else 0.0,
            "Te_max_eV": float(Te.max()), "ne_max": float(ne.max()), "iters": it + 1, "converged": bool(dn < tol * 10),
            "z": z, "Te": Te, "phi": phi, "ne": ne, "nN2": nN2, "nN": nN, "B": B}


# ------------------------------------------------------------------------ the two validation thrusters (cited geometry)
ECHT = dict(r_in_m=0.040, r_out_m=0.050, L_m=0.086, wall="BN")            # Marchioni & Cappelli 2021 (86 mm, 10 mm, 100 mm OD)
P5 = dict(r_in_m=0.0615, r_out_m=0.0865, L_m=0.032, wall="BN_SiO2", B_max_T=0.013)   # Brabston et al. 2025; OD 173 / width 25 mm
