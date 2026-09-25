"""Phase 3b — source coupling (items 12, 13), interstage transport (14), reduced Hall channel (15, 17, 18),
cathode (22).

All models are reduced-order and calibrated where anchors exist (Marchioni & Cappelli 2021 N2 extended-channel
Hall; SPT-100 Xe; ECRA-class ECR sources; AMPCAT). Anomalous electron transport is a free coefficient.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .constants import E_CHARGE, K_B, AMU, M_SPECIES, G0
from .materials import DB
from .plasma_chem import Chamber, solve_global, M_ION, M_NEUT, k_rate, eps_c

ME = 9.10938e-31
EPS0 = 8.854e-12
MU0 = 4e-7 * math.pi

# ----------------------------------------------------------------------------------------------- sources

@dataclass
class ECRSource:
    f_Hz: float = 2.45e9
    P_dc_W: float = 250.0
    eta_dc_mw: float = 0.65        # magnetron / SSPA efficiency
    eta_feed: float = 0.90         # waveguide/coax/isolator losses
    B_res_T: float = 0.0875
    p_min_Pa: float = 2e-3
    overdense_penalty: float = 0.35   # absorbed-power fraction retained per decade of n_e/n_c above 1 (whistler access)

    def absorbed(self, p_Pa: float, n_e: float | None = None) -> tuple[float, float]:
        """(P_absorbed, coupling efficiency). Pressure gate + overdense degradation."""
        gate = 1.0 / (1.0 + (self.p_min_Pa / max(p_Pa, 1e-9)) ** 2)
        eta = self.eta_dc_mw * self.eta_feed * gate
        if n_e:
            n_c = ME * EPS0 * (2 * math.pi * self.f_Hz) ** 2 / E_CHARGE ** 2
            if n_e > n_c:
                eta *= self.overdense_penalty ** math.log10(n_e / n_c)
        return self.P_dc_W * eta, eta


@dataclass
class RFSource:
    f_Hz: float = 13.56e6
    P_dc_W: float = 250.0
    eta_dc_rf: float = 0.80
    R_coil_ohm: float = 0.3
    p_min_Pa: float = 5e-2
    k_plasma_R: float = 6.0e-10    # R_plasma ≈ k * sqrt(n_e) * p^0.3  (ohm) — collisional/stochastic mix, literature-class

    def absorbed(self, p_Pa: float, n_e: float | None = None) -> tuple[float, float]:
        gate = 1.0 / (1.0 + (self.p_min_Pa / max(p_Pa, 1e-9)) ** 2)
        R_p = self.k_plasma_R * math.sqrt(max(n_e or 1e16, 1e14)) * max(p_Pa, 1e-4) ** 0.3
        eta = self.eta_dc_rf * gate * R_p / (R_p + self.R_coil_ohm)
        return self.P_dc_W * eta, eta


# ----------------------------------------------------------------------------------------------- interstage

@dataclass
class Interstage:
    length_m: float = 0.03
    radius_m: float = 0.03
    B_axial_T: float = 0.02
    wall_material: str = "Al2O3_anodised"
    potential_barrier_V: float = 2.0   # entrance sheath/plasma-potential mismatch

    def transport(self, Te_eV: float, ion_mix: dict, p_Pa: float, T_gas_K: float = 500.0) -> dict:
        """Fraction of ions entering that reach the Hall channel entrance."""
        A_wall = 2 * math.pi * self.radius_m * self.length_m
        V = math.pi * self.radius_m ** 2 * self.length_m
        n_g = p_Pa / (K_B * T_gas_K)
        eta = {}
        for i, f in ion_mix.items():
            m = M_ION[i]
            u_B = math.sqrt(E_CHARGE * Te_eV / m)
            # cross-field ion loss reduced by magnetisation: h_eff = h / (1 + (omega_ci * tau_in)^2)
            omega_ci = E_CHARGE * self.B_axial_T / m
            sigma_in = 1.0e-18                    # ion-neutral (CX + elastic) m^2
            tau_in = 1.0 / max(n_g * sigma_in * u_B, 1e-9)
            h = 0.4 / (1.0 + (omega_ci * tau_in) ** 2)
            transit = self.length_m / u_B
            loss_rate = h * u_B * A_wall / V
            surv_wall = math.exp(-loss_rate * transit)
            # barrier: Boltzmann fraction of ions with directed energy > barrier (ions ~ Bohm energy Te/2)
            surv_bar = math.exp(-self.potential_barrier_V / max(0.5 * Te_eV, 0.1))
            # charge exchange in the interstage neutral gas
            surv_cx = math.exp(-n_g * 1.0e-19 * self.length_m)
            eta[i] = surv_wall * surv_bar * surv_cx
        tot = sum(ion_mix.values()) or 1.0
        return {"eta_by_ion": eta, "eta_transport": sum(eta[i] * ion_mix[i] for i in eta) / tot}


# ----------------------------------------------------------------------------------------------- Hall channel
# Numerical resolution of the coupled Hall solver (convergence studies double these)
NUMERICS = {"hall_n_grid": 90, "hall_T_scan": 48, "hall_bisect": 40}

# Coupled (n_e, T_e) model calibration against the one atmospheric anchor (Marchioni & Cappelli 2021, N2 2 mg/s,
# 250 V): 20.8 mN / 834 W / 1061 s / eta_b 0.65 / T_e 30 eV. Thrust is steep in alpha (0.8 -> 1.0: 13 -> 24 mN).
COUPLED_ALPHA_ANOM = 0.88
COUPLED_L_IZ_FRAC = 0.40


def coupled_channel(**kw) -> "HallChannel":
    return HallChannel(**{"alpha_anom": COUPLED_ALPHA_ANOM, "L_iz_frac": COUPLED_L_IZ_FRAC, **kw})


WALL_ATOM_AMU = {"BN": 12.4, "BN_SiO2": 14.0, "Al2O3_anodised": 20.4, "SiC": 20.0, "Graphite": 12.0, "Quartz": 20.0}


def wall_atom_mass(material: str) -> float:
    return WALL_ATOM_AMU.get(material, 20.0) * AMU


def sigma_cx(neutral: str, E_eV: float) -> float:
    """Resonant charge-exchange cross sections, m^2, Rapp-Francis form (a - b ln E)^2 with E in eV.
    Anchors: O+/O ~1.1e-19 at 100 eV; N2+/N2 ~2.6e-19; O2+/O2 ~2.4e-19; Xe+/Xe ~5.5e-19 (300 eV)."""
    E = max(E_eV, 1.0)
    a, b = {"O": (4.3e-10, 0.20e-10), "N2": (6.2e-10, 0.28e-10), "O2": (6.0e-10, 0.28e-10), "N": (4.3e-10, 0.20e-10),
            "Xe": (8.7e-10, 0.30e-10)}.get(neutral, (5.0e-10, 0.25e-10))
    return (a - b * math.log(E)) ** 2

@dataclass
class HallChannel:
    L_m: float = 0.10              # channel length (extended-channel class, Marchioni & Cappelli)
    r_in_m: float = 0.020
    r_out_m: float = 0.035
    B_max_T: float = 0.020
    wall_material: str = "BN"
    alpha_anom: float = 0.15       # anomalous Bohm coefficient (calibrated with the coupled T_e model: Marchioni N2)
    Te_frac_of_Vd: float = 0.10    # peak T_e ≈ frac * V_d, capped by SEE saturation
    Te_iz_frac: float = 0.6        # average T_e over the ionisation zone relative to peak
    L_iz_frac: float = 0.35        # ionisation-zone length as fraction of channel length (extended channel)
    eta_v_base: float = 0.85       # voltage utilisation (ions born inside the acceleration region)
    div_half_angle_deg: float = 22.0
    plume_neutral_len_m: float = 0.10
    magnetic_shielding: float = 0.08   # wall ion-flux fraction relative to unshielded (0.05-0.15 for shielded designs)
    L_acc_m: float = 0.033             # acceleration-zone length, set by the B-field gradient (not the channel length)

    @property
    def area(self):
        return math.pi * (self.r_out_m ** 2 - self.r_in_m ** 2)

    def Te_see_limit(self) -> float:
        """Space-charge-saturated sheath: T_e where SEE yield reaches ~1 (Vaughan-lite from materials DB)."""
        m = DB[self.wall_material]
        # delta(E) = dmax (E/Emax) exp(1 - E/Emax); electrons hit the wall with ~2 Te; solve delta(2Te)=1
        lo, hi = 1.0, 80.0
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if m.see_yield(2 * mid) >= 1.0:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi) if m.see_yield(2 * hi) >= 1.0 else 80.0

    def run(self, Vd: float, neutral_in_kgps: dict, preion_A: dict, T_gas_K: float = 900.0, Te_override=None) -> dict:
        """Steady ionisation + acceleration. neutral_in_kgps by neutral species; preion_A ion current by ion species
        arriving from the interstage (already counted as ions, they are accelerated with eta_v_base)."""
        A = self.area
        Te = min(self.Te_frac_of_Vd * Vd, self.Te_see_limit()) if Te_override is None else Te_override
        Te_iz = self.Te_iz_frac * Te
        # neutral velocity through the channel (thermal, ~ c_bar/2 directed) and residence
        # electron density from current continuity: I_d ≈ I_b + I_e,back ; use anomalous mobility to get n_e
        # Iterate: guess n_e, compute ionisation of each neutral species along L, beam current, then n_e from
        # n_e = I_b / (e u_i A) averaged in the ionisation zone (u_i ~ 0.3 * final), and electron current
        # via mobility mu = alpha_anom / (16 B) (Bohm-like), I_e = e n_e mu E A with E ~ Vd/L_acc.
        n_e = 3e18                     # start high: converge to the sustained (upper) fixed point if it exists
        for _ in range(80):
            I_b = {i: preion_A.get(i, 0.0) for i in M_ION}
            neut_out = {}
            for s, md in neutral_in_kgps.items():
                if md <= 0:
                    continue
                m = M_NEUT[s]
                v_n = math.sqrt(8 * K_B * T_gas_K / (math.pi * m)) / 2.0
                tau = self.L_iz_frac * self.L_m / v_n
                k_tot = k_rate(s, "iz", Te_iz) + (k_rate(s, "diz", Te_iz) if (s, "diz") in RATES_HAS else 0.0)
                f_iz = 1.0 - math.exp(-n_e * k_tot * tau)
                n_in = md / m                       # molecules/s
                n_ion = n_in * f_iz
                neut_out[s] = md * (1 - f_iz)
                if s == "Xe":
                    I_b["Xe+"] += E_CHARGE * n_ion
                elif s == "O2":
                    f_diz = k_rate("O2", "diz", Te_iz) / max(k_tot, 1e-30)
                    I_b["O2+"] += E_CHARGE * n_ion * (1 - f_diz); I_b["O+"] += E_CHARGE * n_ion * f_diz
                elif s == "N2":
                    I_b["N2+"] += E_CHARGE * n_ion
                elif s == "O":
                    I_b["O+"] += E_CHARGE * n_ion
                elif s == "N":
                    I_b["N+"] += E_CHARGE * n_ion
            I_beam = sum(I_b.values())
            # mean ion mass and exit velocity
            if I_beam <= 0:
                break
            m_mean = sum(I_b[i] * M_ION[i] for i in I_b) / I_beam
            u_i = math.sqrt(2 * E_CHARGE * Vd * self.eta_v_base / m_mean)
            u_iz = math.sqrt(E_CHARGE * Te_iz / m_mean)              # ions leave the ionisation zone at ~Bohm speed
            n_e_new = I_beam / (E_CHARGE * u_iz * A)
            if abs(n_e_new - n_e) < 1e-3 * n_e:
                n_e = n_e_new; break
            n_e = 0.5 * (n_e + n_e_new)
        # electron back-current via anomalous mobility across B_max region (length ~ L/3)
        mu_e = self.alpha_anom / (16.0 * self.B_max_T)
        L_acc = self.L_m / 3.0
        n_e_acc = I_beam / (E_CHARGE * u_i * A) if I_beam > 0 else 0.0     # acceleration zone: fast ions, low density
        I_e = E_CHARGE * n_e_acc * mu_e * (Vd / L_acc) * A
        I_d = I_beam + I_e
        eta_b = I_beam / I_d if I_d > 0 else 0.0
        # charge exchange in the near plume: fast ion + slow neutral -> slow ion + fast neutral (thrust lost).
        # Neutral density from the *neutral* directed velocity (~c_bar/2 at T_gas), species-resolved sigma_CX(E).
        f_cx = 0.0
        if I_beam > 0 and neut_out:
            tau_cx = 0.0
            for s_n, md_n in neut_out.items():
                v_n = math.sqrt(8 * K_B * T_gas_K / (math.pi * M_NEUT[s_n])) / 2.0
                n_n = md_n / M_NEUT[s_n] / (v_n * A)
                E_ion = Vd * self.eta_v_base
                tau_cx += n_n * sigma_cx(s_n, E_ion) * self.plume_neutral_len_m
            # CEX conserves momentum to first order (the fast neutral carries it on); thrust is lost only through the
            # slow ions being deflected out of the beam and the fast neutrals' wider divergence: ~25 % of CEX events.
            f_cx = 0.25 * (1.0 - math.exp(-tau_cx))
        cos_div = 0.5 * (1 + math.cos(math.radians(self.div_half_angle_deg)))
        # thrust and kinetic power per ion species (item 11: jet power from the exhaust, not T^2/2mdot)
        T = 0.0; kin = {}
        for i, I in I_b.items():
            if I <= 0: continue
            v = math.sqrt(2 * E_CHARGE * Vd * self.eta_v_base / M_ION[i])
            T += (I / E_CHARGE) * M_ION[i] * v * cos_div * (1 - f_cx)
            kin[i] = 0.5 * (I / E_CHARGE) * M_ION[i] * v * v
        P_d = I_d * Vd
        # wall sputter/erosion proxy: ion flux to walls ~ n_e u_B * A_wall * h ; energy ~ 5 Te
        m = DB[self.wall_material]
        A_wall = 2 * math.pi * (self.r_in_m + self.r_out_m) * self.L_m
        Gamma_w = n_e * math.sqrt(E_CHARGE * Te / (m_mean if I_beam > 0 else 28 * AMU)) * 0.2 * A_wall * self.magnetic_shielding
        Y = m.sputter_yield(5.0 * Te + 20.0)      # sheath-accelerated ions plus ~20 V presheath/oscillation energy
        erosion_kg_s = Gamma_w * Y * wall_atom_mass(self.wall_material)
        erosion_um_per_kh = erosion_kg_s / (m.density * A_wall) * 3600e3 * 1e6
        util = 1.0 - sum(neut_out.values()) / max(sum(neutral_in_kgps.values()), 1e-30)
        return {"Te_eV": Te, "Te_see_limit_eV": self.Te_see_limit(), "n_e": n_e, "I_beam_A": I_beam, "I_beam_by_ion": I_b,
                "I_d_A": I_d, "I_e_back_A": I_e, "eta_b": eta_b, "util_hall": util, "f_cx": f_cx, "cos_div": cos_div,
                "T_N": T, "P_d_W": P_d, "neutral_out_kgps": neut_out, "m_ion_mean_amu": (m_mean / AMU) if I_beam > 0 else 0,
                "wall_erosion_um_per_kh": erosion_um_per_kh, "wall_material": self.wall_material,
                "P_jet_W": sum(kin.values()), "beam_species_kin_W": kin}


RATES_HAS = {("O2", "diz")}


# ----------------------------------------------------------------------------------------------- cathode

@dataclass
class LaB6Cathode:
    emitter_area_m2: float = 3.0e-4
    phi0_eV: float = 2.66
    A_richardson: float = 29.0e4       # A/m^2/K^2 (effective for LaB6 ~ 29 A/cm^2K^2)
    delta_phi_poison_eV: float = 0.9   # work-function rise at full O coverage
    E_des_eV: float = 3.2              # O desorption energy from LaB6 surface
    nu_des_Hz: float = 1e13
    s0_stick: float = 0.3
    xe_shield_mgps: float = 0.05       # cathode Xe flow
    shield_attenuation: float = 1e-3   # O partial pressure at the emitter / ambient, for an orificed cathode with Xe flow
    k_clean_nu_Hz: float = 1e13
    E_clean_eV: float = 5.0            # oxide removal (evaporation/ion cleaning) activation
    heater_W: float = 30.0
    keeper_W: float = 15.0
    evap_A: float = 3.4e7              # evaporation prefactor kg/m2/s (1e-9 kg/m2/s at 1800 K)
    evap_E_eV: float = 5.9             # LaB6 evaporation activation (literature-class)
    thickness_limit_m: float = 1.0e-3

    def coverage(self, p_O_Pa: float, T_K: float) -> float:
        """Oxide coverage from irreversible oxidation vs. thermal/ion cleaning:
        s0 * flux * (1 - theta) = nu exp(-E_clean/kT) * theta * N_s   (N_s = surface site density)."""
        N_s = 1.0e19
        flux = p_O_Pa / math.sqrt(2 * math.pi * M_NEUT["O"] * K_B * 300.0)
        ads = self.s0_stick * flux
        des = self.k_clean_nu_Hz * math.exp(-self.E_clean_eV * E_CHARGE / (K_B * T_K)) * N_s
        return ads / (ads + des)

    def operate(self, I_req_A: float, p_O_ambient_Pa: float) -> dict:
        p_O = p_O_ambient_Pa * (self.shield_attenuation if self.xe_shield_mgps > 0 else 1.0)
        # find emitter temperature that delivers I_req with the poisoned work function
        lo, hi = 1200.0, 2200.0
        for _ in range(60):
            T = 0.5 * (lo + hi)
            th = self.coverage(p_O, T)
            phi = self.phi0_eV + self.delta_phi_poison_eV * th
            J = self.A_richardson * T * T * math.exp(-phi * E_CHARGE / (K_B * T))
            if J * self.emitter_area_m2 >= I_req_A:
                hi = T
            else:
                lo = T
        T = hi; th = self.coverage(p_O, T); phi = self.phi0_eV + self.delta_phi_poison_eV * th
        evap = self.evap_A * math.exp(-self.evap_E_eV * E_CHARGE / (K_B * T))        # kg/m2/s
        life_h = self.thickness_limit_m * DB["LaB6"].density / max(evap, 1e-30) / 3600.0
        return {"T_emitter_K": T, "coverage": th, "phi_eV": phi, "p_O_at_emitter_Pa": p_O,
                "life_h_evaporation": life_h, "P_W": self.heater_W * (T / 1700.0) ** 4 * 0.6 + self.keeper_W,
                "xe_mgps": self.xe_shield_mgps, "ok": T < 2000.0}


# ----------------------------------------------------------------------------------------------- Hall ignition / bifurcation
def hall_fixed_points(channel: "HallChannel", Vd: float, neutral_in_kgps: dict, preion_A: dict | None = None,
                      n_grid=None, T_gas_K: float = 900.0) -> dict:
    """Map the discharge as n_e -> F(n_e) = I_beam(n_e) / (e u_iz A) and find its fixed points (F(n) = n).
    Stable branches have dF/dn < 1 at the crossing; the unstable crossing is the ignition threshold: the seed
    density (keeper/cathode plume, or a pre-ioniser) must exceed it for the discharge to reach the upper branch.
    Returns branches, threshold and the seed needed."""
    import numpy as np
    preion_A = preion_A or {}
    A = channel.area
    Te = min(channel.Te_frac_of_Vd * Vd, channel.Te_see_limit()); Te_iz = channel.Te_iz_frac * Te
    grid = n_grid if n_grid is not None else np.logspace(14, 19.5, 120)

    def F(n_e):
        I_b = {i: preion_A.get(i, 0.0) for i in M_ION}
        for s, md in neutral_in_kgps.items():
            if md <= 0: continue
            m = M_NEUT[s]
            v_n = math.sqrt(8 * K_B * T_gas_K / (math.pi * m)) / 2.0
            tau = channel.L_iz_frac * channel.L_m / v_n
            k_tot = k_rate(s, "iz", Te_iz) + (k_rate(s, "diz", Te_iz) if (s, "diz") in RATES_HAS else 0.0)
            f_iz = 1.0 - math.exp(-n_e * k_tot * tau)
            n_ion = md / m * f_iz
            ion = "Xe+" if s == "Xe" else "N2+" if s == "N2" else "O+" if s == "O" else "N+" if s == "N" else "O2+"
            I_b[ion] += E_CHARGE * n_ion
        I_beam = sum(I_b.values())
        if I_beam <= 0: return 0.0
        m_mean = sum(I_b[i] * M_ION[i] for i in I_b) / I_beam
        u_iz = math.sqrt(E_CHARGE * Te_iz / m_mean)
        return I_beam / (E_CHARGE * u_iz * A)

    Fv = np.array([F(n) for n in grid]); g = Fv - grid
    crossings = []
    for i in range(len(grid) - 1):
        if g[i] == 0 or g[i] * g[i + 1] < 0:
            n_c = math.sqrt(grid[i] * grid[i + 1])
            slope = (Fv[i + 1] - Fv[i]) / (grid[i + 1] - grid[i])
            crossings.append((n_c, "stable" if slope < 1 else "unstable"))
    seed_preion = sum(preion_A.values()) / (E_CHARGE * math.sqrt(E_CHARGE * Te_iz / (22 * AMU)) * A) if preion_A else 0.0
    upper = [c for c in crossings if c[1] == "stable" and c[0] > 1e16]
    unstable = [c for c in crossings if c[1] == "unstable"]
    n_threshold = unstable[0][0] if unstable else None
    n_seed_keeper = 3e16          # keeper/cathode plume density reaching the channel exit (literature-class prior)
    return {"crossings": crossings, "has_upper_branch": bool(upper), "n_upper": upper[-1][0] if upper else None,
            "n_threshold": n_threshold, "n_seed_keeper": n_seed_keeper, "n_seed_preion": seed_preion,
            "ignites_from_keeper": bool(upper) and (n_threshold is None or n_seed_keeper >= n_threshold),
            "ignites_with_preion": bool(upper) and (n_threshold is None or (n_seed_keeper + seed_preion) >= n_threshold),
            "F_at_seed_over_seed": F(n_seed_keeper) / n_seed_keeper, "Te_iz_eV": Te_iz}


# ----------------------------------------------------------------------------------------------- coupled n_e, T_e Hall discharge
ME_KG = 9.10938e-31


def _sheath_drop(Te: float, delta: float, m_i: float) -> float:
    """Floating sheath with secondary emission (Hobbs & Wesson): phi = Te ln((1-delta) sqrt(m_i/(2 pi m_e)));
    space-charge saturated at delta >= 0.983 -> ~1.02 Te."""
    if delta >= 0.983:
        return 1.02 * Te
    return Te * math.log((1.0 - delta) * math.sqrt(m_i / (2 * math.pi * ME_KG)))


def hall_discharge_transient(ch: "HallChannel", Vd: float, neutral_in_kgps: dict, preion_A: dict | None = None,
                             n0: float = 1e14, T0: float = 3.0, I_seed_A: float = 0.10, t_end: float = 3e-3,
                             T_gas_K: float = 900.0, h_wall_iz: float = 0.05, n_grid: int = 160) -> dict:
    """0-D two-zone Hall discharge with a solved electron-energy balance.
    Electrons equilibrate in ~us, so T_e is quasi-steady: for each plasma density n it is the root of
        (I_e(n,T) + I_seed) V_d = e R_iz(n,T_iz) eps_c(T_iz) + e G_w (2T + phi_s(T, delta_SEE)) + 2.5 T (I_e + I_seed)
    (T_iz = Te_iz_frac T; I_e from Bohm anomalous mobility in the acceleration zone; I_seed = cathode electron
    current reaching the anode through the unignited channel). Density then follows
        V_iz dn/dt = g(n) = R_iz(n, T(n)) + I_pre/e - n u_B (A + h A_wall,iz).
    Fixed points of g: stable where g' < 0. Ignition from cold (n0) requires g > 0 on the whole path [n0, n_upper];
    a stable low root below n_upper means the channel stays dark (needs a larger seed / pre-ioniser); two stable
    roots = hysteresis (lit if started hot, dark if started cold)."""
    import numpy as np
    preion_A = preion_A or {}
    A = ch.area; L_iz = ch.L_iz_frac * ch.L_m; L_acc = min(ch.L_acc_m, ch.L_m / 2.0)
    V_iz = A * L_iz
    A_w_iz = 2 * math.pi * (ch.r_in_m + ch.r_out_m) * L_iz
    A_w_acc = 2 * math.pi * (ch.r_in_m + ch.r_out_m) * L_acc
    wall = DB[ch.wall_material]
    mu = ch.alpha_anom / (16.0 * ch.B_max_T)
    species = [s for s, md in neutral_in_kgps.items() if md > 0]
    Nin = {s: neutral_in_kgps[s] / M_NEUT[s] for s in species}
    tau = {s: L_iz / (math.sqrt(8 * K_B * T_gas_K / (math.pi * M_NEUT[s])) / 2.0) for s in species}
    I_pre = sum(preion_A.values())
    T_cap = 0.5 * Vd

    def rates(n, T_iz):
        R = {}; cost = 0.0
        for sp in species:
            k = k_rate(sp, "iz", T_iz) + (k_rate(sp, "diz", T_iz) if (sp, "diz") in RATES_HAS else 0.0)
            R[sp] = Nin[sp] * (1.0 - math.exp(-n * k * tau[sp]))
            cost += R[sp] * eps_c(sp, T_iz)
        return R, cost

    def balance(n, T):
        T_iz = ch.Te_iz_frac * T
        R, cost = rates(n, T_iz)
        Rtot = sum(R.values())
        m_mean = (sum(R[sp] * M_NEUT[sp] for sp in R) / Rtot) if Rtot > 0 else 22 * AMU
        u_B = math.sqrt(E_CHARGE * T_iz / m_mean)
        I_b = E_CHARGE * n * u_B * A
        u_i = math.sqrt(2 * E_CHARGE * Vd * ch.eta_v_base / m_mean)
        n_acc = I_b / (E_CHARGE * u_i * A)
        I_e = E_CHARGE * n_acc * mu * (Vd / L_acc) * A
        delta = min(wall.see_yield(2 * T), 0.99)
        phi_s = _sheath_drop(T, delta, m_mean)
        Gw = n_acc * math.sqrt(E_CHARGE * T / m_mean) * 0.2 * A_w_acc + n * u_B * h_wall_iz * A_w_iz
        P_in = (I_e + I_seed_A) * Vd
        P_out = E_CHARGE * cost + E_CHARGE * Gw * (2 * T + phi_s) + 2.5 * T * (I_e + I_seed_A)
        return P_in - P_out, Rtot, u_B, m_mean

    T_scan = np.logspace(math.log10(0.5), math.log10(T_cap), NUMERICS["hall_T_scan"])

    def T_of_n(n):
        """Deterministic branch selection: all stable electron-energy roots (net heating + below, - above) are found
        on a fixed T grid; the hottest one (field-heated branch) is followed, then refined by bisection."""
        Ts = list(T_scan); vals = [balance(n, T)[0] for T in Ts]
        # local refinement: where |balance| dips toward zero between scan points without a sign change, a close pair
        # of roots may hide inside; rescan that interval densely (catches pairs down to ~0.3 % separation)
        extra = []
        for i in range(1, len(Ts) - 1):
            if vals[i - 1] * vals[i] > 0 and vals[i] * vals[i + 1] > 0 and abs(vals[i]) < abs(vals[i - 1]) and abs(vals[i]) < abs(vals[i + 1]):
                for T in np.logspace(math.log10(Ts[i - 1]), math.log10(Ts[i + 1]), 40)[1:-1]:
                    extra.append((T, balance(n, T)[0]))
        if extra:
            merged = sorted(list(zip(Ts, vals)) + extra)
            Ts = [m[0] for m in merged]; vals = [m[1] for m in merged]
        if vals[-1] > 0:
            return T_cap
        idx = [i for i in range(len(Ts) - 1) if vals[i] > 0 and vals[i + 1] <= 0]
        if not idx:
            return Ts[0]
        i = idx[-1]; lo, hi = Ts[i], Ts[i + 1]
        for _ in range(30):
            mid = math.sqrt(lo * hi)
            if balance(n, mid)[0] > 0: lo = mid
            else: hi = mid
        return math.sqrt(lo * hi)

    def g(n):
        T = T_of_n(n)
        _, Rtot, u_B, _ = balance(n, T)
        return (Rtot + I_pre / E_CHARGE - n * u_B * (A + h_wall_iz * A_w_iz)) / V_iz, T

    grid = np.logspace(math.log10(n0), 19.7, NUMERICS["hall_n_grid"])
    gv = []; Tv = []
    for n in grid:
        a, T = g(n); gv.append(a); Tv.append(T)
    gv = np.array(gv); Tv = np.array(Tv)
    roots = []
    for i in range(len(grid) - 1):
        if gv[i] > 0 and gv[i + 1] <= 0:
            roots.append((math.sqrt(grid[i] * grid[i + 1]), "stable"))
        elif gv[i] < 0 and gv[i + 1] >= 0:
            roots.append((math.sqrt(grid[i] * grid[i + 1]), "unstable"))
    # refine every stable root by bisection on g (grid spacing alone is ~8 % in n)
    refined = []
    for (nr, kind) in roots:
        if kind != "stable":
            refined.append((nr, kind)); continue
        lo, hi = nr / 10 ** 0.04, nr * 10 ** 0.04
        if g(lo)[0] > 0 and g(hi)[0] <= 0:
            for _ in range(NUMERICS["hall_bisect"]):
                mid = math.sqrt(lo * hi)
                if g(mid)[0] > 0: lo = mid
                else: hi = mid
            nr = math.sqrt(lo * hi)
        refined.append((nr, kind))
    roots = refined
    stable = [r for r in roots if r[1] == "stable"]
    upper = [r for r in stable if r[0] > 1e16]
    n_upper = upper[-1][0] if upper else None
    # cold start: follow g from n0 upward until the first stable root; lit if that root is a plasma branch (> 1e16)
    first_stable = stable[0][0] if stable else None
    lit_branches = [r[0] for r in stable if r[0] > 1e16]
    ignited = bool(lit_branches) and first_stable is not None and first_stable > 1e16 and gv[0] > 0
    hysteresis = len(lit_branches) >= 2
    n_cold = first_stable if ignited else None
    n_end = first_stable if (first_stable and gv[0] > 0) else n0
    T_end = float(np.interp(math.log10(n_end), np.log10(grid), Tv))
    def state_at(n_root):
        T_u = T_of_n(n_root); n_upper_ = n_root
        T_iz = ch.Te_iz_frac * T_u
        R, cost = rates(n_upper_, T_iz)
        _, Rtot, u_B, m_mean = balance(n_upper_, T_u)
        I_b_tot = E_CHARGE * n_upper_ * u_B * A
        u_i = math.sqrt(2 * E_CHARGE * Vd * ch.eta_v_base / m_mean)
        n_acc = I_b_tot / (E_CHARGE * u_i * A)
        I_e = E_CHARGE * n_acc * mu * (Vd / L_acc) * A
        exit_frac = A / (A + h_wall_iz * A_w_iz)
        ion_of = {"Xe": "Xe+", "N2": "N2+", "O": "O+", "N": "N+", "O2": "O2+"}
        I_by = {i: preion_A.get(i, 0.0) for i in M_ION}
        for sp, Rs in R.items():
            if sp == "O2":
                kd = k_rate("O2", "diz", T_iz); ki = k_rate("O2", "iz", T_iz); fd = kd / (kd + ki)
                I_by["O+"] += E_CHARGE * Rs * exit_frac * fd; I_by["O2+"] += E_CHARGE * Rs * exit_frac * (1 - fd)
            else:
                I_by[ion_of[sp]] += E_CHARGE * Rs * exit_frac
        return {"n": n_root, "T_e": T_u, "R": R, "I_by": I_by, "I_e": I_e, "n_acc": n_acc, "m_mean": m_mean, "u_B": u_B,
                "neut_out": {sp: (Nin[sp] - R[sp]) * M_NEUT[sp] for sp in species}, "A_w_acc": A_w_acc}

    state = state_at(n_upper) if n_upper else None                 # hot (highest) branch
    state_cold = state_at(n_cold) if n_cold else None              # branch reached from a cold start
    return {"n_e": n_end, "Te_eV": T_end, "ignited": bool(ignited), "has_upper_branch": n_upper is not None, "n_upper": n_upper,
            "T_upper": state["T_e"] if state else None, "state": state, "state_cold": state_cold, "n_cold": n_cold,
            "hysteresis": bool(hysteresis), "roots": roots, "settled": True, "n_grid": grid, "g_grid": gv, "T_grid": Tv}


def hall_run_coupled(ch: "HallChannel", Vd: float, neutral_in_kgps: dict, preion_A: dict | None = None, T_gas_K: float = 900.0,
                     n0: float = 1e14, I_seed_A: float = 0.10, start: str = "cold") -> dict:
    """Operating point entirely from the coupled (n_e, T_e) solution: beam current by species from the ionisation
    rates at the refined upper root, electron back-current from the same energy-balance closure, then acceleration,
    CEX, thrust, jet power and wall erosion. (start='hot' reports the upper branch even if a cold start fails.)"""
    preion_A = preion_A or {}
    tr = hall_discharge_transient(ch, Vd, neutral_in_kgps, preion_A, n0=n0, I_seed_A=I_seed_A, T_gas_K=T_gas_K)
    lit = tr["has_upper_branch"] if start == "hot" else tr["ignited"]
    st_sel = (tr["state"] if start == "hot" else tr["state_cold"]) if lit else None
    if not lit:
        return {"Te_eV": tr["Te_eV"], "Te_see_limit_eV": ch.Te_see_limit(), "n_e": tr["n_e"], "I_beam_A": 0.0, "I_beam_by_ion": {i: 0.0 for i in M_ION},
                "I_d_A": I_seed_A, "I_e_back_A": 0.0, "eta_b": 0.0, "util_hall": 0.0, "f_cx": 0.0, "cos_div": 1.0, "T_N": 0.0,
                "P_d_W": I_seed_A * Vd, "neutral_out_kgps": dict(neutral_in_kgps), "m_ion_mean_amu": 0.0, "wall_erosion_um_per_kh": 0.0,
                "wall_material": ch.wall_material, "ignited": False, "energy_model": "coupled", "P_jet_W": 0.0, "beam_species_kin_W": {}}
    st = st_sel; A = ch.area
    I_b = st["I_by"]; I_beam = sum(I_b.values()); I_e = st["I_e"]; I_d = I_beam + I_e
    neut_out = st["neut_out"]
    cos_div = 0.5 * (1 + math.cos(math.radians(ch.div_half_angle_deg)))
    tau_cx = 0.0
    for sp, md in neut_out.items():
        if md <= 0: continue
        v_n = math.sqrt(8 * K_B * T_gas_K / (math.pi * M_NEUT[sp])) / 2.0
        tau_cx += md / M_NEUT[sp] / (v_n * A) * sigma_cx(sp, Vd * ch.eta_v_base) * ch.plume_neutral_len_m
    f_cx = 0.25 * (1.0 - math.exp(-tau_cx))
    T = 0.0; kin = {}
    for i, I in I_b.items():
        if I <= 0: continue
        v = math.sqrt(2 * E_CHARGE * Vd * ch.eta_v_base / M_ION[i])
        T += (I / E_CHARGE) * M_ION[i] * v * cos_div * (1 - f_cx)
        kin[i] = 0.5 * (I / E_CHARGE) * M_ION[i] * v * v
    m = DB[ch.wall_material]; Te = st["T_e"]
    Gamma_w = st["n_acc"] * math.sqrt(E_CHARGE * Te / st["m_mean"]) * 0.2 * st["A_w_acc"] * ch.magnetic_shielding
    Y = m.sputter_yield(5.0 * Te + 20.0)
    A_wall = 2 * math.pi * (ch.r_in_m + ch.r_out_m) * ch.L_m
    erosion = Gamma_w * Y * wall_atom_mass(ch.wall_material) / (m.density * A_wall) * 3600e3 * 1e6
    util = 1.0 - sum(neut_out.values()) / max(sum(neutral_in_kgps.values()), 1e-30)
    return {"Te_eV": Te, "Te_see_limit_eV": ch.Te_see_limit(), "n_e": st["n"], "I_beam_A": I_beam, "I_beam_by_ion": I_b,
            "mode": ("high" if abs(st["n"] - (tr["n_upper"] or 0)) < 1e-6 * st["n"] else "low"),
            "I_d_A": I_d, "I_e_back_A": I_e, "eta_b": I_beam / I_d if I_d > 0 else 0.0, "util_hall": util, "f_cx": f_cx, "cos_div": cos_div,
            "T_N": T, "P_d_W": I_d * Vd, "neutral_out_kgps": neut_out, "m_ion_mean_amu": st["m_mean"] / AMU,
            "wall_erosion_um_per_kh": erosion, "wall_material": ch.wall_material, "ignited": True, "energy_model": "coupled",
            "P_jet_W": sum(kin.values()), "beam_species_kin_W": kin, "hysteresis": tr["hysteresis"]}
