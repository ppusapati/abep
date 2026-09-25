"""Modular propulsion architecture engine (replaces cards for architecture selection).

    capture -> compression/storage -> IONIZER -> ACCELERATOR -> NEUTRALIZER -> exhaust

Stages declare interfaces (input/output state, pressure / density / flow ranges, whether they need a neutralizer);
the enumerator connects only compatible stages. Every valid architecture runs through the same chain:
gas path (Phases 1-2) -> ionisation (global model, Phase 3) -> accelerator physics (this module) -> neutralizer ->
power (PPU maps) -> thermal -> life -> mass -> spacecraft T/D and mission ROM. Research mode reports the RFP
gates as flags but ranks on physics objectives.

Accelerator physics (reduced-order, literature-anchored):
  hall       HallChannel (Phase 3)
  grids      Child-Langmuir extraction J = (4 eps0/9) sqrt(2e/m) V^1.5 / d^2 * transparency; beam limited by the
             ion source current; accel-grid CEX erosion life; needs neutralizer
  nozzle     magnetic nozzle: ion energy ≈ k_amb * T_e (k ≈ 5-7 from electron cooling), divergence ~30°; no neutralizer
  mpd        Maecker: T = (mu0/4pi) I^2 (ln(ra/rc) + 0.75) + electrothermal term; V ≈ 25-60 V; onset limit I^2/mdot
  pit        pulsed inductive: eta(E_pulse) = 0.35 E/(E + 2 kJ), Isp 2500 s; capacitor bank mass 0.3 J/g
  thermal    resistojet / arcjet / microwave-electrothermal: v_e = sqrt(2 eta_n cp T0), T0 by heater/material limit
FEEP, electrospray, PPT are represented with air_compatible=False (liquid/solid propellant) and are reported as such.
"""
from __future__ import annotations
import math, itertools
from dataclasses import dataclass, field
import pandas as pd
from .constants import E_CHARGE, K_B, AMU, G0, RFP
from .plasma_chem import Chamber, solve_global, M_ION, M_NEUT
from .plasma_devices import HallChannel, ECRSource, RFSource, Interstage, LaB6Cathode
from .materials import DB

EPS0 = 8.854e-12; MU0 = 4e-7 * math.pi


@dataclass
class Ionizer:
    name: str
    output: str                 # "plasma" | "neutral" | "internal" (accelerator ionises itself)
    p_min_Pa: float
    wall_factor: float          # magnetised-wall loss factor in the global model
    source_kind: str            # "ecr" | "rf" | "dc" | "arc" | "none"
    dc_eff: float
    mass_kg: float
    ic: float
    electrodes_in_plasma: bool  # O-poisoning / erosion exposure
    note: str = ""


@dataclass
class Accelerator:
    name: str
    input: tuple                # accepted input states
    family: str
    needs_neutralizer: bool
    air_compatible: bool
    mass_kg: float
    ic: float
    V_typ: float
    note: str = ""
    self_ionizing: bool = False # can run on neutral gas with its own internal ionisation
    mga: float = 0.30           # mass growth allowance by maturity


@dataclass
class Neutralizer:
    name: str
    xe_mgps: float
    air_mgps: float
    power_W: float
    mass_kg: float
    o_exposed: bool
    ic: float
    mga: float = 0.15

    def operate(self, I_req_A: float, p_O_plume_Pa: float) -> dict:
        """Current capability and life. LaB6: Phase-3 model. Plasma-bridge cathodes (RF / microwave on air):
        extracted electron current I = e n_e u_B A_orifice * k_extract with n_e from a small global discharge on the
        cathode flow; power scales with required current; life from O erosion of the orifice/antenna (materials DB)."""
        if self.name == "lab6_xe":
            c = LaB6Cathode().operate(max(I_req_A, 0.5), p_O_plume_Pa)
            return {"I_max_A": 12.0 * (self.xe_mgps / 0.05), "P_W": c["P_W"], "life_h": c["life_h_evaporation"], "T_K": c["T_emitter_K"],
                    "ok": I_req_A <= 12.0 and c["ok"]}
        if self.name == "none":
            return {"I_max_A": 0.0, "P_W": 0.0, "life_h": 1e9, "ok": True}
        # plasma-bridge cathode on air: discharge in a 5 cm^3 cavity, orifice 3 mm, absorbed power grows with current demand
        A_or = math.pi * (1.5e-3) ** 2
        flows = {"O": self.air_mgps * 1e-6 * 0.45, "N2": self.air_mgps * 1e-6 * 0.45, "O2": self.air_mgps * 1e-6 * 0.10}
        ch = Chamber(volume_m3=5e-6, wall_area_m2=1.5e-3, exit_area_m2=A_or, magnetised_wall_factor=0.6 if self.name == "mw_air" else 1.0)
        best = None
        for P_abs in (20, 40, 70, 100, 150, 220, 300):
            st = solve_global(ch, flows, P_abs)
            u_B = math.sqrt(E_CHARGE * st.Te_eV / (22 * AMU))
            I_max = E_CHARGE * st.n_e * u_B * A_or * 55.0          # extraction factor calibrated to AMPCAT: 0.8 A at 145 W, 0.1 mg/s air
            best = (P_abs, st, I_max)
            if I_max >= I_req_A * 1.2:
                break
        P_abs, st, I_max_pred = best
        # item 29: predicted vs validated. AMPCAT demonstrated ~0.8 A (hours); no air RF cathode data in the package.
        I_validated = {"mw_air": 1.0, "rf_cathode": 0.5}.get(self.name, I_max_pred)
        I_max = min(I_max_pred, I_validated)
        eff = 0.65 if self.name == "mw_air" else 0.75
        # O erosion: orifice/antenna faces ion flux at ~4 T_e; material SiC (mw) / alumina insulator + Mo tip (rf)
        mat = DB["SiC"] if self.name == "mw_air" else DB["Mo"]
        flux = st.n_e * math.sqrt(E_CHARGE * st.Te_eV / (22 * AMU)) * 0.3
        Y = mat.sputter_yield(3.0 * st.Te_eV + 10.0)               # floating-wall sheath ~3 Te + presheath
        rate_m_s = flux * Y * (40 * AMU) / mat.density
        life_h = (0.5e-3 / max(rate_m_s, 1e-30)) / 3600.0
        life_h = min(life_h, 30000.0 if self.name == "mw_air" else 20000.0)   # data ceiling: hours-class demonstrations only
        return {"I_max_A": I_max, "I_max_predicted_A": I_max_pred, "I_max_validated_A": I_validated,
                "P_W": P_abs / eff + 10.0, "life_h": life_h, "life_validated_h": 10.0, "Te_eV": st.Te_eV, "n_e": st.n_e,
                "ok": I_max >= I_req_A}


IONIZERS = [
    Ionizer("hall_internal", "hall_internal", 1.5e-2, 1.0, "none", 1.0, 0.0, 1.0, True, "ionisation inside the Hall channel"),
    Ionizer("self", "self", 0.0, 1.0, "none", 1.0, 0.0, 1.0, False, "accelerator ionises its own propellant"),
    Ionizer("dc_discharge", "plasma", 3e-2, 1.0, "dc", 0.9, 1.2, 0.9, True, "Kaufman-type; cathode in the O plasma"),
    Ionizer("rf_icp", "plasma", 5e-2, 0.5, "rf", 0.8, 2.5, 0.8, False, "13.56 MHz inductive"),
    Ionizer("helicon", "plasma", 3e-2, 0.3, "rf", 0.75, 3.0, 0.75, False, "helicon with axial B"),
    Ionizer("ecr", "plasma", 2e-3, 0.3, "ecr", 0.65, 3.0, 0.70, False, "2.45 GHz ECR"),
    Ionizer("arc", "neutral_hot", 5e2, 1.0, "arc", 0.9, 0.8, 0.9, True, "arc heater; needs ~kPa"),
]
ACCELERATORS = [
    Accelerator("hall", ("hall_internal", "plasma"), "hall", True, True, 0.0, 0.85, 275.0, "E x B, extended channel", True, 0.15),
    Accelerator("grids", ("plasma",), "grids", True, True, 1.8, 0.55, 1200.0, "electrostatic grids", False, 0.20),
    Accelerator("mag_nozzle", ("plasma",), "nozzle", False, True, 0.6, 0.8, 0.0, "ambipolar magnetic nozzle", False, 0.30),
    Accelerator("mpd", ("plasma", "self"), "mpd", False, True, 2.5, 0.85, 40.0, "Lorentz-force", True, 0.30),
    Accelerator("pit", ("plasma", "self"), "pit", False, True, 3.0, 0.8, 0.0, "pulsed inductive", True, 0.30),
    Accelerator("resistojet", ("self",), "thermal", False, True, 0.4, 0.95, 0.0, "resistive heater + nozzle", True, 0.10),
    Accelerator("arcjet", ("neutral_hot",), "thermal", False, True, 0.6, 0.9, 0.0, "arc heater + nozzle", False, 0.20),
    Accelerator("met_nozzle", ("plasma",), "thermal", False, True, 0.6, 0.85, 0.0, "microwave/RF electrothermal + nozzle", False, 0.30),
    Accelerator("feep", (), "feep", True, False, 0.5, 0.5, 8000.0, "liquid-metal field emission", False, 0.3),
    Accelerator("electrospray", (), "electrospray", True, False, 0.5, 0.5, 2000.0, "ionic liquid", False, 0.3),
    Accelerator("ppt", (), "ppt", False, False, 1.0, 0.8, 0.0, "solid-propellant pulsed plasma", False, 0.3),
]
NEUTRALIZERS = [
    Neutralizer("lab6_xe", 0.05, 0.0, 45.0, 1.1, False, 0.85, 0.15),
    Neutralizer("mw_air", 0.0, 0.10, 145.0, 1.3, True, 0.75, 0.30),
    Neutralizer("rf_cathode", 0.0, 0.05, 60.0, 1.0, True, 0.8, 0.30),
    Neutralizer("none", 0.0, 0.0, 0.0, 0.0, False, 1.0, 0.0),
]


def enumerate_architectures() -> list[dict]:
    archs = []
    for io, ac, ne in itertools.product(IONIZERS, ACCELERATORS, NEUTRALIZERS):
        if not ac.air_compatible:
            if io.name == "hall_internal" and ne.name == "none":
                archs.append({"ionizer": io, "accelerator": ac, "neutralizer": ne, "valid": False, "reason": "propellant is liquid/solid: not air-compatible"})
            continue
        if io.output not in ac.input:
            continue
        if io.output == "self" and not ac.self_ionizing:
            continue
        if ac.needs_neutralizer and ne.name == "none":
            continue
        if not ac.needs_neutralizer and ne.name != "none":
            continue
        archs.append({"ionizer": io, "accelerator": ac, "neutralizer": ne, "valid": True, "reason": ""})
    return archs


def arch_name(a: dict) -> str:
    return f"{a['ionizer'].name}+{a['accelerator'].name}" + (f"+{a['neutralizer'].name}" if a["neutralizer"].name != "none" else "")


# ------------------------------------------------------------------------------------------ accelerator physics
_ION_CACHE: dict = {}
_NEUT_CACHE: dict = {}


def _ion_source(io: Ionizer, flows: dict, p_in: float, P_dc: float, exit_area_m2: float = 3.0e-3, wall_factor: float | None = None):
    key = (io.name, round(p_in, 5), round(P_dc, 1), tuple(round(v * 1e9, 3) for v in flows.values()), round(exit_area_m2, 5),
           None if wall_factor is None else round(wall_factor, 3))
    if key in _ION_CACHE:
        return _ION_CACHE[key]
    # evaluate at the rounded key values so the cached result is a pure function of the key (call-order independent)
    flows_k = {sp: v for sp, v in zip(flows.keys(), (round(v * 1e9, 3) / 1e9 for v in flows.values()))}
    out = _ion_source_impl(io, flows_k, round(p_in, 5), round(P_dc, 1), round(exit_area_m2, 5),
                           None if wall_factor is None else round(wall_factor, 3))
    _ION_CACHE[key] = out
    return out


def _chamber(io, exit_area_m2, wall_factor):
    # chamber volume / wall scale with the extraction area (a 10 cm-class source for ~3e-3 m^2)
    r = max(math.sqrt(exit_area_m2 / math.pi), 0.02)
    L = 2.0 * r
    V = math.pi * r * r * L; A_w = 2 * math.pi * r * L + math.pi * r * r
    return Chamber(magnetised_wall_factor=io.wall_factor if wall_factor is None else wall_factor, volume_m3=max(V, 3e-4),
                   wall_area_m2=max(A_w, 0.02), exit_area_m2=exit_area_m2)


def _ion_source_impl(io: Ionizer, flows: dict, p_in: float, P_dc: float, exit_area_m2: float = 3.0e-3, wall_factor=None):
    if io.source_kind == "ecr":
        src = ECRSource(P_dc_W=P_dc); ch = _chamber(io, exit_area_m2, wall_factor)
        st = solve_global(ch, flows, src.absorbed(p_in)[0], f_cutoff_Hz=2.45e9)
        st = solve_global(ch, flows, src.absorbed(p_in, st.n_e)[0], f_cutoff_Hz=2.45e9)
    elif io.source_kind == "rf":
        src = RFSource(P_dc_W=P_dc, p_min_Pa=io.p_min_Pa); ch = _chamber(io, exit_area_m2, wall_factor)
        st = solve_global(ch, flows, src.absorbed(p_in, 3e17)[0])
        st = solve_global(ch, flows, src.absorbed(p_in, st.n_e)[0])
    else:   # dc discharge: absorbed = P_dc * eff, cathode-limited
        ch = _chamber(io, exit_area_m2, wall_factor)
        st = solve_global(ch, flows, P_dc * io.dc_eff)
    if not st.sustained:
        raise ValueError(f"source plasma not sustained (Te pinned at {st.Te_eV:.1f} eV or utilisation {st.util_total:.2f} > 1): envelope")
    cbar = {s: math.sqrt(8 * K_B * ch.T_gas_K / (math.pi * M_NEUT[s])) for s in M_NEUT}
    neut_out = {s: st.n_neut.get(s, 0.0) * ch.exit_neutral_K * ch.exit_area_m2 * cbar[s] / 4.0 * M_NEUT[s] for s in ("O", "O2", "N2", "N")}
    m_in = sum(flows.values()); m_out = sum(neut_out.values()) + sum(st.ion_exit_A[i] / E_CHARGE * M_ION[i] for i in st.ion_exit_A)
    if m_in > 0 and abs(m_out / m_in - 1.0) > 0.02:
        raise ValueError(f"source mass balance residual {m_out / m_in - 1:+.1%}: envelope")
    return st, neut_out


def _energy_transfer(m_ion_kg: float, m_target_amu: float = 95.95) -> float:
    mt = m_target_amu * AMU
    return 4 * m_ion_kg * mt / (m_ion_kg + mt) ** 2


def grid_optics(st, neut_out_kgps: dict, V_b: float, A_grid_m2: float, gap_m: float = 1.0e-3, r_s_m: float = 0.95e-3,
                phi_screen: float = 0.67, phi_accel: float = 0.24, t_accel_m: float = 0.5e-3, R_V: float = 0.85,
                T_gas_K: float = 500.0) -> dict:
    """Two-grid ion optics, species-resolved (document 16, item 27).
    Extraction: available ion current = sum_i J_Bohm,i * A_grid * phi_screen (from the source plasma state);
    per-beamlet Child-Langmuir limit with the mixture effective mass (sum f_i / sqrt(m_i))^-2 and effective
    length l_e = sqrt(g^2 + r_s^2) at total voltage V_T = V_b / R_V. Normalised perveance P = I/I_CL sets beamlet
    divergence (min near 0.7) and direct impingement (crossover below ~0.3, edge above 1). Electron backstreaming:
    the accel voltage |V_a| = V_T - V_b must exceed ~0.1 V_b + 40 V. Charge exchange from the actual neutral flux
    through the grids (neutral transparency phi_accel), species sigma_CX(E), CEX ions striking the accel grid at
    ~|V_a| + 0.2 V_b; Mo sputtering scaled by the energy-transfer factor of each ion species relative to Xe.
    Accel-grid life = time to remove half of the web mass."""
    from .plasma_devices import sigma_cx
    V_T = V_b / R_V; V_a = V_T - V_b
    bs_ok = V_a >= 0.1 * V_b + 40.0
    I_src = sum(st.ion_exit_A.values())
    if I_src <= 0:
        return {"T_N": 0.0, "I_b_A": 0.0, "P_accel_W": 0.0, "life_h": 1e9, "ok": False}
    frac = {i: st.ion_exit_A[i] / I_src for i in st.ion_exit_A}
    # current density at the screen from the source (ion exit current spread over the chamber exit = grid area)
    J_src = I_src / max(A_grid_m2, 1e-9)
    I_avail = J_src * A_grid_m2 * phi_screen
    m_eff = (sum(frac[i] / math.sqrt(M_ION[i]) for i in frac) ** -2)
    l_e = math.sqrt(gap_m ** 2 + r_s_m ** 2)
    J_CL = (4 * EPS0 / 9) * math.sqrt(2 * E_CHARGE / m_eff) * V_T ** 1.5 / l_e ** 2
    I_CL = J_CL * A_grid_m2 * phi_screen
    P_hat = I_avail / I_CL
    I_b = min(I_avail, I_CL)
    div_deg = 10.0 + 30.0 * (P_hat - 0.7) ** 2 if P_hat < 1.3 else 20.8 + 40.0 * (P_hat - 1.3)
    f_imp = (0.3 * (0.3 - P_hat) / 0.3 if P_hat < 0.3 else 0.0) + (0.5 * (P_hat - 1.0) if P_hat > 1.0 else 0.0)
    f_imp = min(f_imp, 0.5)
    I_imp = f_imp * I_b
    # neutrals downstream of the screen: flux through the grid set at thermal speed, density in the intergrid gap
    n_n = {}
    for sp, md in neut_out_kgps.items():
        if md <= 0: continue
        v4 = math.sqrt(8 * K_B * T_gas_K / (math.pi * M_NEUT[sp])) / 4.0
        n_n[sp] = (md / M_NEUT[sp]) / (v4 * A_grid_m2 * phi_screen) * phi_accel / 0.5
    L_cx = gap_m + 3 * t_accel_m
    E_beam = V_T
    f_cx = sum(n * sigma_cx(sp, E_beam) * L_cx for sp, n in n_n.items())
    I_cx = f_cx * I_b
    # sputtering of the accel grid (Mo), species-resolved via energy-transfer factor vs Xe
    E_imp = V_a + 0.2 * V_b
    gamma_xe = _energy_transfer(131.3 * AMU)
    Y = sum(frac[i] * DB["Mo"].sputter_yield(E_imp) * _energy_transfer(M_ION[i]) / gamma_xe for i in frac)
    Y_direct = sum(frac[i] * DB["Mo"].sputter_yield(V_T) * _energy_transfer(M_ION[i]) / gamma_xe for i in frac)
    rate_kg_s = ((I_cx / E_CHARGE) * Y + (I_imp / E_CHARGE) * Y_direct) * 95.95 * AMU
    m_web = t_accel_m * A_grid_m2 * (1 - phi_accel) * DB["Mo"].density
    life_h = 0.5 * m_web / max(rate_kg_s, 1e-30) / 3600.0
    cos_div = 0.5 * (1 + math.cos(math.radians(min(div_deg, 80.0))))
    T = sum((I_b * frac[i] / E_CHARGE) * M_ION[i] * math.sqrt(2 * E_CHARGE * V_b / M_ION[i]) for i in frac) * cos_div * (1 - 0.25 * min(f_cx, 1.0))
    P_accel = I_b * V_b + (I_imp + I_cx) * V_T
    return {"T_N": T, "I_b_A": I_b, "P_accel_W": P_accel, "life_h": life_h, "P_hat": P_hat, "div_deg": div_deg, "f_imp": f_imp,
            "f_cx": f_cx, "V_a": V_a, "backstreaming_ok": bs_ok, "space_charge_limited": P_hat > 1.0, "ok": bs_ok,
            "P_jet_W": sum(0.5 * (I_b * frac[i] / E_CHARGE) * M_ION[i] * 2 * E_CHARGE * V_b / M_ION[i] for i in frac) * cos_div}


NOZZLE_ENERGY_BOUND = {"on": False}     # True: rank the nozzle with the energy-bound (most favourable electron model)


def magnetic_nozzle(st, B0_T: float, R_m: float, A_throat_m2: float, gamma_poly: float = 1.2, BH_max: float = 2.0e5) -> dict:
    """Magnetic nozzle (document 16, item 28). The plume's energy comes from the source power partition: each exiting
    ion carries the Bohm energy 0.5 T_e plus the electron enthalpy converted by the ambipolar field in a polytropic
    expansion (gamma ~1.2) to the detachment density n0/R_m:  E_i = T_e [0.5 + gamma/(gamma-1) (1 - R_m^(1-gamma))].
    Detachment efficiency eta_det = 1 - 0.9 / sqrt(R_m); divergence narrows with R_m. Permanent-magnet ring sized by
    energy product for B0 over a field volume ~ throat radius^3 x R_m^(1/3) (the expansion length), plus leakage."""
    I = sum(st.ion_exit_A.values())
    if I <= 0:
        return {"T_N": 0.0, "I_b_A": 0.0, "P_accel_W": 0.0, "life_h": 6e4, "magnet_kg": 0.0, "P_jet_W": 0.0}
    Te = st.Te_eV
    E_i = Te * (0.5 + gamma_poly / (gamma_poly - 1) * (1 - R_m ** (1 - gamma_poly)))
    eta_det = max(1 - 0.9 / math.sqrt(R_m), 0.0)
    div = 45.0 / (1 + 0.05 * R_m)
    cos_div = 0.5 * (1 + math.cos(math.radians(div)))
    T = sum((st.ion_exit_A[i] / E_CHARGE) * M_ION[i] * math.sqrt(2 * E_CHARGE * E_i / M_ION[i]) for i in st.ion_exit_A) * eta_det * cos_div
    P_jet = sum(0.5 * (st.ion_exit_A[i] / E_CHARGE) * 2 * E_CHARGE * E_i for i in st.ion_exit_A) * eta_det * cos_div
    # energy bound: every watt not spent on ionisation/excitation/dissociation becomes directed ion energy (as if wall and
    # exit electron losses were entirely recovered by a hot-electron population and the ambipolar field)
    P_kin_max = max(st.P_abs_W - st.power["ionisation_excitation_W"] - st.power["dissociation_W"], 0.0)
    mdot_i = sum(st.ion_exit_A[i] / E_CHARGE * M_ION[i] for i in st.ion_exit_A)
    T_bound = math.sqrt(2 * mdot_i * P_kin_max) * eta_det * cos_div
    if NOZZLE_ENERGY_BOUND["on"]:
        T = T_bound; P_jet = P_kin_max * eta_det * cos_div
    r_t = math.sqrt(A_throat_m2 / math.pi)
    # stored field energy is concentrated where B ~ B0: a throat region ~ pi r_t^2 x 4 r_t (downstream B falls ~1/R_m)
    V_field = math.pi * r_t ** 2 * (4 * r_t)
    W_field = B0_T ** 2 / (2 * MU0) * V_field
    V_mag = 2.0 * 2 * W_field / BH_max                     # magnet volume from energy product, leakage 2
    m_mag = V_mag * DB["SmCo_bare"].density + 0.3 + 0.15 * (r_t / 0.02)       # + pole pieces / housing
    return {"T_N": T, "I_b_A": I, "P_accel_W": 0.0, "life_h": 6e4, "E_i_eV": E_i, "eta_det": eta_det, "div_deg": div,
            "magnet_kg": m_mag, "P_jet_W": P_jet, "T_bound_N": T_bound}


def accel_grids(st, V_b: float = 1200.0, d_gap_m: float = 1.0e-3, A_grid_m2: float = 3.0e-3, transparency: float = 0.7,
                div_deg: float = 12.0, p_in: float = 0.05) -> dict:
    I_src = sum(st.ion_exit_A.values())
    tot = I_src or 1e-30
    m_mean = sum(st.ion_exit_A[i] * M_ION[i] for i in st.ion_exit_A) / tot
    J_cl = (4 * EPS0 / 9) * math.sqrt(2 * E_CHARGE / m_mean) * V_b ** 1.5 / d_gap_m ** 2
    I_cl = J_cl * A_grid_m2 * transparency
    I_b = min(I_src * transparency, I_cl)
    scale = I_b / tot
    cos_div = 0.5 * (1 + math.cos(math.radians(div_deg)))
    n_n = p_in / (K_B * 500.0)
    f_cx = 1 - math.exp(-n_n * 1e-19 * 0.05)
    T = sum((st.ion_exit_A[i] * scale / E_CHARGE) * M_ION[i] * math.sqrt(2 * E_CHARGE * V_b / M_ION[i]) for i in st.ion_exit_A) * cos_div * (1 - f_cx)
    P_beam = I_b * V_b; P_drain = 0.03 * I_b * (V_b + 200)
    # accel grid CEX erosion: CEX ions ~ f_cx * I_b at ~V_accel 200 V onto Mo grid 0.5 mm
    Y = DB["Mo"].sputter_yield(250.0)
    rate_kg_s = f_cx * I_b / E_CHARGE * Y * 96 * AMU * 0.3
    life_h = (0.5e-3 * A_grid_m2 * (1 - transparency) * DB["Mo"].density) / max(rate_kg_s, 1e-30) / 3600.0
    return {"T_N": T, "I_b_A": I_b, "P_accel_W": P_beam + P_drain, "space_charge_limited": I_cl < I_src * transparency,
            "f_cx": f_cx, "life_h": life_h, "V_b": V_b, "m_ion_amu": m_mean / AMU}


def accel_nozzle(st, k_amb: float = 6.0, div_deg: float = 30.0) -> dict:
    I = sum(st.ion_exit_A.values()); cos_div = 0.5 * (1 + math.cos(math.radians(div_deg)))
    T = sum((st.ion_exit_A[i] / E_CHARGE) * M_ION[i] * math.sqrt(2 * E_CHARGE * k_amb * st.Te_eV / M_ION[i]) for i in st.ion_exit_A) * cos_div
    return {"T_N": T, "I_b_A": I, "P_accel_W": 0.0, "life_h": 60000.0, "V_eff": k_amb * st.Te_eV}


def accel_mpd(flow_kgps: float, P_W: float, V: float = 40.0, ra_rc: float = 3.0, chi_i: float = 0.0, Te_eV: float = 3.0) -> dict:
    """Self-field MPD. Voltage = ionisation/sheath drop (falls with pre-ionisation fraction chi_i) + resistive drop
    (plasma conductivity from T_e, Spitzer-like) + back-EMF. Pre-ionised inflow lowers the ionisation cost and the
    onset current (less neutral depletion at the anode)."""
    V_ion = 20.0 * (1.0 - chi_i) + 8.0                       # V spent ionising the flow
    sigma = 1.9e4 * Te_eV ** 1.5 / 10.0                      # S/m, Spitzer with ln(Lambda)=10
    R_plasma = 0.05 / max(sigma, 1.0) / 1e-3                  # ~5 cm path over ~1e-3 m^2
    I = 0.0
    for _ in range(40):                                       # solve P = I (V_ion + I R + V_emf)
        # back-EMF = u_exhaust * B_self * L: with B ~ mu0 I/(2 pi r), V_emf ≈ (mu0/2pi) ln(ra/rc) I u_e
        u_e = math.sqrt((MU0 / (4 * math.pi)) * I ** 2 * (math.log(ra_rc) + 0.75) / max(flow_kgps, 1e-12))
        V_emf = (MU0 / (2 * math.pi)) * math.log(ra_rc) * I * u_e + 5.0
        V_tot = V_ion + I * R_plasma + V_emf
        I_new = P_W / max(V_tot, 1.0)
        if abs(I_new - I) < 1e-3: I = I_new; break
        I = 0.5 * (I + I_new)
    T_em = (MU0 / (4 * math.pi)) * I ** 2 * (math.log(ra_rc) + 0.75)
    T_et = flow_kgps * 3000.0 * 0.3
    onset_param = I ** 2 / max(flow_kgps, 1e-12)
    onset = onset_param > 3e10 * (1 + chi_i)
    return {"T_N": T_em + T_et, "I_A": I, "V_A": V_tot, "V_emf": V_emf, "P_accel_W": P_W, "life_h": 2000.0 if onset else 8000.0,
            "onset": onset, "sigma_S_m": sigma}


def accel_pit(flow_kgps: float, P_avg_W: float, E_pulse_J: float = 100.0, Isp_s: float = 2500.0, chi_i: float = 0.0) -> dict:
    """Pulsed inductive: eta(E) from the coupling-energy scaling, raised by pre-ionisation (current sheet forms
    without a breakdown delay: 0.6 + 0.4 chi_i)."""
    eta = 0.35 * E_pulse_J / (E_pulse_J + 2000.0) * (0.6 + 0.4 * chi_i)
    v_e = Isp_s * G0
    T = 2 * eta * P_avg_W / v_e
    mdot_needed = T / v_e
    if mdot_needed > flow_kgps:            # flow-limited: cannot sustain the Isp; lower Isp
        v_e = 2 * eta * P_avg_W / flow_kgps ** 1 / 1.0
        v_e = math.sqrt(2 * eta * P_avg_W / flow_kgps); T = flow_kgps * v_e
    f_pulse = P_avg_W / E_pulse_J
    return {"T_N": T, "eta": eta, "P_accel_W": P_avg_W, "life_h": min(1e9 / max(f_pulse, 1e-9) / 3600.0, 30000.0),
            "cap_bank_kg": E_pulse_J / 300.0 + 1.0, "pulse_Hz": f_pulse}


def accel_thermal(flow_kgps: float, P_W: float, kind: str, m_mean: float = 22 * AMU, chi_i: float = 0.0, Te_eV: float = 0.0) -> dict:
    """Electrothermal nozzle. Enthalpy per kg = eta_heat * P / mdot, capped by the material/chamber limit; above ~3000 K
    part of the enthalpy sits in dissociation (frozen-flow loss ~35 % for air). Plasma-fed variants (MET/RF/helicon)
    receive the plasma's electron energy 3/2 n_e k T_e as recoverable enthalpy only partially (recombination on walls)."""
    T0 = {"resistojet": 1500.0, "arcjet": 3500.0, "met": 2500.0, "rf_et": 2200.0, "helicon_et": 2500.0}[kind]
    cp = 3.5 * K_B / m_mean
    eta_n = 0.85; eta_heat = {"resistojet": 0.9, "arcjet": 0.35, "met": 0.5, "rf_et": 0.45, "helicon_et": 0.5}[kind]
    h_el = eta_heat * P_W / max(flow_kgps, 1e-12)
    # plasma-fed variants: the ionised fraction carries 1.5 k T_e per electron + ionisation energy, recovered on
    # recombination at the walls/nozzle with ~50 % efficiency (rest radiated/lost)
    if chi_i > 0 and Te_eV > 0:
        h_el += 0.5 * chi_i * (1.5 * Te_eV + 14.0) * E_CHARGE / m_mean
    h = min(h_el, cp * T0)
    frozen = 0.35 if h / cp > 3000.0 else 0.1
    v_e = math.sqrt(2 * eta_n * h * (1 - frozen))
    return {"T_N": flow_kgps * v_e, "v_e": v_e, "P_accel_W": P_W, "T0_K": h / cp, "frozen_loss": frozen,
            "life_h": {"resistojet": 20000.0, "arcjet": 1500.0, "met": 10000.0, "rf_et": 15000.0, "helicon_et": 15000.0}[kind]}


# ------------------------------------------------------------------------------------------ calibration envelopes (item 8)
CALIBRATION = {
    # family: (anchor description, envelope dict) — only data actually in the package
    "hall": ("Marchioni & Cappelli 2021 N2 extended channel; SPT-100 Xe",
             {"mdot_mgps": (1.5, 2.5), "Vd": (200.0, 300.0), "P_W": (400.0, 900.0), "Isp_s": (800.0, 1400.0)}),
    "grids": ("none (screening model)", {}), "nozzle": ("none (screening model)", {}), "mpd": ("none", {}),
    "pit": ("none", {}), "thermal": ("none", {}),
}


def calibration_status(family: str, point: dict) -> tuple[str, float]:
    """'interpolation' | 'extrapolation' | 'uncalibrated', and the worst relative excursion outside the envelope."""
    anchor, env = CALIBRATION.get(family, ("none", {}))
    if not env:
        return "uncalibrated", float("inf")
    worst = 0.0
    for k, (lo, hi) in env.items():
        v = point.get(k)
        if v is None: continue
        if v < lo: worst = max(worst, (lo - v) / lo)
        elif v > hi: worst = max(worst, (v - hi) / hi)
    return ("interpolation" if worst == 0.0 else "extrapolation"), worst


# ------------------------------------------------------------------------------------------ closure of one architecture
@dataclass
class DesignConstraints:
    """Physics limits are always enforced inside the models; these are *design* constraints, user-selectable.
    The RFP is one preset (rfp_preset())."""
    P_bus_max_W: float = 1500.0
    m_max_kg: float | None = None
    T_min_mN: float | None = None
    T_max_mN: float | None = None
    life_min_h: float | None = None
    no_extrapolation: bool = False     # reject candidates outside the propulsion calibration envelope
    max_extrapolation: float | None = None   # reject candidates further than this relative excursion outside it


def rfp_preset() -> DesignConstraints:
    return DesignConstraints(P_bus_max_W=RFP.power_max_W, m_max_kg=RFP.mass_max_kg, T_min_mN=RFP.thrust_min_mN,
                             T_max_mN=RFP.thrust_max_mN, life_min_h=RFP.ignition_hours)


def _propulsion(a: dict, gas: dict, x: dict) -> dict:
    """One propulsion operating point for architecture a with variables x. Returns thrust, powers, states, life items."""
    io, ac, ne = a["ionizer"], a["accelerator"], a["neutralizer"]
    md_cap = gas["mdot_air"]; p_in = gas["p_in"]
    md = max(md_cap - ne.air_mgps * 1e-6, 0.0)          # an air-fed cathode is fed from the captured air (mass balance)
    flows = {"O": md * gas["fO"], "N2": md * gas["fN2"], "O2": md * gas["fO2"]}
    st = None; chi = 0.0; P_ion = x.get("P_ion", 0.0); life_items = {}; res = {}
    if io.output == "plasma" and P_ion > 0 and not (io.p_min_Pa <= p_in <= 1e3):
        raise ValueError(f"ionizer {io.name} pressure envelope: p_in {p_in:.3g} Pa outside [{io.p_min_Pa:.3g}, 1e3]")
    if io.output == "neutral_hot" and p_in < io.p_min_Pa:
        raise ValueError(f"ionizer {io.name} needs >= {io.p_min_Pa:.0f} Pa, has {p_in:.3g} Pa")
    neut = flows
    exit_area = x.get("A_grid", x.get("A_throat", 3.0e-3))
    wall_f = None
    if ac.family == "nozzle":                        # axial field confines the source plasma: stronger B, lower wall loss
        wall_f = min(max(io.wall_factor * math.sqrt(0.0875 / x["B0"]), 0.05), 1.0)
        if io.source_kind == "ecr" and x["B0"] < 0.0875:
            raise ValueError("ECR resonance needs B0 >= 0.0875 T in the source (envelope)")
    if io.output == "plasma" and P_ion > 0:
        st, neut = _ion_source(io, flows, p_in, P_ion, exit_area, wall_f)
        chi = st.util_total
    elif io.output == "plasma" and ac.family != "hall":
        raise ValueError("plasma-fed accelerator needs P_ion > 0")
    if ac.family == "hall":
        preion = {}
        if st is not None:
            tot = sum(st.ion_exit_A.values()) or 1.0
            tr = Interstage().transport(st.Te_eV, {i: st.ion_exit_A[i] / tot for i in st.ion_exit_A}, p_in)
            preion = {i: st.ion_exit_A[i] * tr["eta_by_ion"][i] for i in st.ion_exit_A}
            flows = dict(neut)
            # ions lost in the interstage recombine on its walls and continue as neutrals (mass conserved)
            back = {"O+": "O", "O2+": "O2", "N2+": "N2", "N+": "N", "Xe+": "Xe"}
            for i, I in st.ion_exit_A.items():
                lost = I * (1.0 - tr["eta_by_ion"][i]) / E_CHARGE * M_ION[i]
                if lost > 0:
                    flows[back[i]] = flows.get(back[i], 0.0) + lost
        from .plasma_devices import hall_run_coupled, coupled_channel
        ov = {k: v for k, v in HALL_OVERRIDES.items() if k != "start"}
        hr = hall_run_coupled(coupled_channel(L_m=x["L_ch"], magnetic_shielding=0.03, **ov), x["Vd"], flows, preion,
                              start=HALL_OVERRIDES.get("start", "cold"))
        if not hr.get("ignited", True):
            raise ValueError("Hall discharge does not ignite from a cold start at this flow/geometry")
        T = hr["T_N"]; P_acc = hr["P_d_W"]; I_neut = hr["I_d_A"]; I_beam = hr["I_beam_A"]
        life_items["hall_channel"] = 6.0e3 / max(hr["wall_erosion_um_per_kh"], 1e-9) * 1e3
        res = {"eta_b": hr["eta_b"], "Te_eV": hr["Te_eV"], "sustained": hr["I_beam_A"] > 0.05, "V": x["Vd"], "P_jet_W": hr["P_jet_W"]}
        m_acc = 1.2 + 3.1 * (x["L_ch"] / 0.2); V_main = x["Vd"]
    elif ac.family == "grids":
        g = grid_optics(st, neut, x["Vb"], x["A_grid"], gap_m=x.get("gap", 1.0e-3))
        if not g["backstreaming_ok"]:
            raise ValueError("electron backstreaming: accel voltage below limit (envelope)")
        T = g["T_N"]; P_acc = g["P_accel_W"]; I_neut = g["I_b_A"]; I_beam = g["I_b_A"]
        life_items["grids"] = g["life_h"]
        res = {"space_charge_limited": g["space_charge_limited"], "P_hat": g["P_hat"], "div_deg": g["div_deg"], "f_cx": g["f_cx"],
               "Te_eV": st.Te_eV, "eV_per_ion_source": st.eV_per_usable_ion, "V": x["Vb"] / 0.85, "P_jet_W": g["P_jet_W"]}
        m_acc = 0.6 + 2 * 0.5e-3 * x["A_grid"] / 0.67 * DB["Mo"].density * 0.5 + 0.8 * (x["A_grid"] / 3e-3) ** 0.5; V_main = x["Vb"] / 0.85
    elif ac.family == "nozzle":
        g = magnetic_nozzle(st, x["B0"], x["R_m"], x["A_throat"]); T = g["T_N"]; P_acc = 0.0; I_neut = 0.0; I_beam = g["I_b_A"]
        life_items["nozzle_source"] = g["life_h"]
        res = {"Te_eV": st.Te_eV, "eV_per_ion_source": st.eV_per_usable_ion, "V": 0.0, "E_i_eV": g["E_i_eV"], "eta_det": g["eta_det"],
               "P_jet_W": g["P_jet_W"]}
        m_acc = ac.mass_kg + g["magnet_kg"]; V_main = 0.0
    elif ac.family == "mpd":
        g = accel_mpd(md, x["P_acc"], chi_i=chi, Te_eV=(st.Te_eV if st else 3.0)); T = g["T_N"]; P_acc = g["P_accel_W"]; I_neut = 0.0; I_beam = 0.0
        life_items["mpd_electrodes"] = g["life_h"]; res = {"I_A": g["I_A"], "V": g["V_A"], "onset": g["onset"], "P_jet_W": 0.5 * T * T / max(md, 1e-12)}
        m_acc = ac.mass_kg; V_main = g["V_A"]
    elif ac.family == "pit":
        g = accel_pit(md, x["P_acc"], E_pulse_J=x["E_pulse"], chi_i=chi); T = g["T_N"]; P_acc = g["P_accel_W"]; I_neut = 0.0; I_beam = 0.0
        life_items["pit_capacitors"] = g["life_h"]; res = {"eta_pit": g["eta"], "pulse_Hz": g["pulse_Hz"], "V": 0.0, "P_jet_W": g["eta"] * x["P_acc"]}
        m_acc = ac.mass_kg + g["cap_bank_kg"]; V_main = 0.0
    elif ac.family == "thermal":
        if ac.name == "resistojet":
            kind = "resistojet"
        elif ac.name == "arcjet":
            kind = "arcjet"
        else:
            kind = {"ecr": "met", "rf_icp": "rf_et", "helicon": "helicon_et", "dc_discharge": "met"}[io.name]
        g = accel_thermal(md, x["P_acc"], kind, chi_i=chi, Te_eV=(st.Te_eV if st else 0.0)); T = g["T_N"]; P_acc = g["P_accel_W"]; I_neut = 0.0; I_beam = 0.0
        life_items["heater_nozzle"] = g["life_h"]; res = {"v_e": g["v_e"], "T0_K": g["T0_K"], "kind": kind, "V": 0.0, "P_jet_W": 0.5 * md * g["v_e"] ** 2}
        m_acc = ac.mass_kg; V_main = 0.0
    else:
        raise ValueError(ac.family)
    # neutralizer closure: current capability and life
    nk = (ne.name, math.ceil(max(I_neut, 0.1) * 4) / 4, round(p_in * gas["fO"], 5))     # 0.25 A bins
    if ne.name in ("mw_air", "rf_cathode"):
        capk = (ne.name, "cap")
        if capk not in _NEUT_CACHE:
            _NEUT_CACHE[capk] = ne.operate(50.0, p_in * gas["fO"] * 0.1)["I_max_A"]      # capability at max source power
        if I_neut > _NEUT_CACHE[capk]:
            cath = {"I_max_A": _NEUT_CACHE[capk], "P_W": 0.0, "life_h": 0.0, "ok": False}
            nk = None
    if nk is not None and nk not in _NEUT_CACHE:
        # evaluate at the bin's upper edge so the cached value is a pure function of the key (no call-order dependence)
        I_bin = nk[1]
        _NEUT_CACHE[nk] = ne.operate(I_bin, p_in * gas["fO"] * 0.1) if ne.name != "none" else {"I_max_A": 0.0, "P_W": 0.0, "life_h": 1e9, "ok": True}
    if nk is not None:
        cath = _NEUT_CACHE[nk]
    if ne.name != "none":
        life_items["neutralizer"] = cath["life_h"]
    return {"T_N": T, "P_ion_W": P_ion, "P_acc_W": P_acc, "P_neut_W": cath["P_W"], "I_neut_req_A": I_neut, "I_neut_max_A": cath["I_max_A"],
            "neut_ok": cath["ok"], "I_beam_A": I_beam, "V_main": V_main, "m_acc": m_acc, "chi_preion": chi, "life_items": life_items,
            "st": st, **res}


HALL_OVERRIDES: dict = {}          # UQ hook: e.g. {"alpha_anom": 0.8}


def P_ion_envelope_violation(io, p_in):
    return io.output == "plasma" and p_in < io.p_min_Pa


def _variables(a: dict) -> dict:
    """Optimisation variables per architecture family (nested optimisation, item 38)."""
    io, ac = a["ionizer"], a["accelerator"]
    v = {}
    if io.output == "plasma":
        v["P_ion"] = ([0.0, 50.0, 100.0, 200.0, 350.0] if ac.family == "hall" else
                      [400.0, 700.0, 1000.0, 1400.0] if ac.family == "nozzle" else [150.0, 300.0, 500.0, 800.0])
    if ac.family == "hall":
        v["Vd"] = [225.0, 250.0, 275.0, 300.0, 325.0]; v["L_ch"] = [0.12, 0.15, 0.20, 0.25, 0.30]
    elif ac.family == "grids":
        v["Vb"] = [600.0, 1000.0, 1500.0, 2000.0]; v["A_grid"] = [1.5e-3, 3e-3, 6e-3, 1.2e-2]; v["gap"] = [0.6e-3, 1.0e-3]
    elif ac.family == "nozzle":
        v["B0"] = [0.0875, 0.25]; v["R_m"] = [20.0, 50.0]; v["A_throat"] = [1e-3, 3e-3, 1e-2]
    elif ac.family in ("mpd", "thermal"):
        v["P_acc"] = [400.0, 800.0, 1200.0]
    elif ac.family == "pit":
        v["P_acc"] = [400.0, 800.0, 1200.0]; v["E_pulse"] = [100.0, 500.0]
    return v


def close_architecture(a: dict, gas_fn, sc, dc: DesignConstraints | None = None, k_margin: float = 1.3,
                       gas_vars: dict | None = None, strict: bool = False, firing_hours: float = RFP.mission_hours,
                       keep_candidates: bool = True, size_arrays: bool = False, mission_envelope: bool = False,
                       envelope_margin: float = 1.1) -> dict:
    """Nested constrained optimisation. gas_fn(area, p_level) -> gas state (gas path is part of the search, item 9).
    Every design constraint, converter rating and thermal feasibility is enforced *inside* the candidate loop
    (item 2, 6, 7). Model exceptions are recorded as MODEL_ERROR, never treated as infeasible (item 3);
    strict=True re-raises them."""
    from .mission_env import spacecraft_drag
    from .atmosphere import atmosphere
    from .ppu import default_ppu, load_modes, Converter
    from .thermal import default_nodes, size_radiator, ThermalParams
    from .mass_bom import xe_tank, hall_magnetic_circuit, hall_channel_mass, build_bom, structure_mass
    dc = dc or DesignConstraints()
    gas_vars = gas_vars or {"area": [0.6, 0.7, 0.85], "p_level": [0.02, 0.05, 0.1]}
    cands = []; runners = []; best_env = None
    io, ac, ne = a["ionizer"], a["accelerator"], a["neutralizer"]
    name = arch_name(a)
    if not a["valid"]:
        return {"architecture": name, "valid": False, "status": "INCOMPATIBLE", "reason": a["reason"]}
    vars_ = _variables(a); keys = list(vars_)
    best = None; n_eval = 0; n_model_err = 0; n_infeasible = 0; last_err = ""; reject = {}
    def rej(k):
        reject[k] = reject.get(k, 0) + 1
    for area in gas_vars["area"]:
        for p_level in gas_vars["p_level"]:
            gas = gas_fn(area, p_level)
            atm = atmosphere(gas["alt"], gas["solar"])
            D_sc0 = spacecraft_drag(sc, atm["rho"], atm.get("V_rel", atm["V"]), gas["area"], gas["C_D"])["D_total_N"]
            D_sc = D_sc0
            for combo in (itertools.product(*(vars_[k] for k in keys)) if keys else [()]):
                x = dict(zip(keys, combo))
                try:
                    pr = _propulsion(a, gas, x)
                except ValueError as e:              # physical infeasibility, recorded with its reason
                    n_infeasible += 1; last_err = str(e)
                    rej("not_ignited" if "ignite" in str(e) else "envelope"); continue
                except Exception as e:
                    n_model_err += 1; last_err = f"{type(e).__name__}: {e}"
                    if strict: raise
                    rej("MODEL_ERROR"); continue
                n_eval += 1
                has_s1 = io.output == "plasma" and pr["P_ion_W"] > 0; s1_kind = "ecr" if io.source_kind == "ecr" else "rf"
                V_conv = max(pr["V_main"], 12.0)
                ppu = default_ppu(V_conv, max(pr["I_beam_A"] / 0.7, pr.get("I_A", 0.0), 1.0), has_s1, s1_kind, pr["P_ion_W"], max(gas["comp_power"], 20.0))
                if ac.family in ("mpd", "pit", "thermal", "nozzle"):
                    ppu.converters = [c for c in ppu.converters if c.name not in ("anode", "keeper", "heater")]
                    if ac.family == "mpd":
                        ppu.converters.append(Converter("mpd_hc", V_conv, pr.get("I_A", 30.0) * 1.2, "anode", P_fixed_W=6, k_cond=0.02, k_sw=0.02, kg_per_kW=2.5, m_base_kg=0.6))
                    elif ac.family == "pit":
                        ppu.converters.append(Converter("cap_charger", 3000.0, pr["P_acc_W"] / 3000.0 * 1.5 + 0.02, "hv_mw", P_fixed_W=5, k_cond=30.0, k_sw=0.03, kg_per_kW=3.0, m_base_kg=0.8))
                    elif ac.family == "thermal":
                        ppu.converters.append(Converter("heater_main", 28.0, pr["P_acc_W"] / 28.0 * 1.3, "heater", P_fixed_W=2, k_cond=0.01, k_sw=0.008, kg_per_kW=1.5, m_base_kg=0.3))
                if ne.name in ("mw_air", "rf_cathode"):      # dedicated converter for plasma-bridge cathodes (item 6)
                    ppu.converters.append(Converter("cathode_src", 50.0, pr["P_neut_W"] / 50.0 * 1.3 + 0.1, "aux", P_fixed_W=2, k_cond=0.1, k_sw=0.015, kg_per_kW=2.2, m_base_kg=0.35))
                P_mag = 25.0 if ac.family in ("hall", "nozzle") or io.source_kind == "ecr" else 0.0
                demand = {"magnet": P_mag / 12.0, "motor": gas["comp_power"] / 48.0, "aux": 1.0}
                if ac.family == "hall": demand["anode"] = pr["P_acc_W"] / V_conv
                if ac.family == "grids": demand["anode"] = pr["P_acc_W"] / V_conv
                if ne.name == "lab6_xe": demand["keeper"] = pr["P_neut_W"] / 30.0
                if ac.family == "mpd": demand["mpd_hc"] = pr.get("I_A", 30.0)
                if ac.family == "pit": demand["cap_charger"] = pr["P_acc_W"] / 3000.0
                if ac.family == "thermal": demand["heater_main"] = pr["P_acc_W"] / 28.0
                if has_s1: demand["hv_mw" if s1_kind == "ecr" else "rf_amp"] = pr["P_ion_W"] / (4000.0 if s1_kind == "ecr" else 50.0)
                if ne.name in ("mw_air", "rf_cathode"): demand["cathode_src"] = pr["P_neut_W"] / 50.0
                loads = ppu.loads(demand)
                P_bus = loads["P_bus_W"]
                # ---- constraints inside the loop
                if not loads["rating_ok"]: rej("converter_rating"); continue
                if P_bus > dc.P_bus_max_W: rej("power"); continue
                if not pr["neut_ok"]: rej("neutralizer_current"); continue
                T = pr["T_N"]
                if dc.T_min_mN is not None and T * 1e3 < dc.T_min_mN: rej("thrust_min"); continue
                if dc.T_max_mN is not None and T * 1e3 > dc.T_max_mN: rej("thrust_max"); continue
                life_items = dict(pr["life_items"]); life_items.update({"blade_coating": gas["blade_life_h"], "intake_coating": gas["intake_life_h"], "bearings": 1e6, "ppu": 1e5})
                life_sys = min(life_items.values())
                if dc.life_min_h is not None and life_sys < dc.life_min_h: rej("life"); continue
                # thermal (canonical), enforced
                P_jet = pr.get("P_jet_W", 0.0)
                # jet energy is drawn from the accelerating supply first; any excess (nozzle, electrothermal-from-plasma)
                # comes out of the source's power — each watt counted once
                from_acc = min(P_jet, pr["P_acc_W"]); from_src = min(P_jet - from_acc, pr["P_ion_W"])
                P_jet = from_acc + from_src
                Q_dev = max(pr["P_acc_W"] - from_acc, 0.0)
                ledger = {"jet": P_jet, "plume": 0.4 * Q_dev, "accelerator_body": 0.6 * Q_dev, "ionizer": pr["P_ion_W"] - from_src,
                          "neutralizer": pr["P_neut_W"], "magnets": P_mag, "compressor": gas["comp_power"], "aux": 5.0,
                          "ppu_loss_control": loads["P_loss_W"]}
                resid = (P_bus - sum(ledger.values())) / P_bus
                if abs(resid) > 0.02: rej("energy_ledger"); continue
                nodes = default_nodes(pr["P_acc_W"], pr["I_beam_A"], pr["V_main"], 0.0, 1.0,
                                      gas["comp_power"], pr["P_neut_W"], loads["P_loss_W"], gas["area"])
                nodes[2].P_int_W = ledger["accelerator_body"]
                nodes[3].P_int_W = P_mag
                nodes[4].P_int_W = ledger["ionizer"]                   # all source power ends as source-wall/magnetron heat, once
                # in-loop: analytic radiator bound (all waste at 330 K, epsilon 0.88, 10 % sun load); full network solve on the winner
                Q = sum(n.P_int_W for n in nodes)
                A_est = Q / (0.88 * 5.67e-8 * (330.0 ** 4 - 4.0 ** 4) * 0.9)
                if A_est > 4.9: rej("thermal"); continue
                rad = {"feasible": True, "A_rad_m2": A_est, "m_thermal_kg": A_est * 4.0 + 0.4 * len(nodes) * 0.15, "P_waste_W": Q, "limiting_node": "estimate", "_nodes": nodes}
                # mass (canonical BOM + structure_mass)
                xe_kg = ne.xe_mgps * 1e-6 * firing_hours * 3600 * 1.2
                parts = {"intake": gas["intake_mass"], "compressor": gas["comp_mass"], "reservoir_feed": 1.1, "ionizer": io.mass_kg,
                         "accelerator": (hall_channel_mass(0.02, 0.035, x["L_ch"]) + hall_magnetic_circuit(0.02, 0.02, 0.035, x["L_ch"])["mass_kg"]) if ac.family == "hall" else pr["m_acc"],
                         "neutralizer": ne.mass_kg, "xe": xe_kg, "xe_tank": xe_tank(max(xe_kg, 0.3))["mass_kg"] if xe_kg > 0 else 0.0,
                         "ppu": ppu.mass(P_bus)["m_ppu_total_kg"], "thermal": rad["m_thermal_kg"]}
                stm = structure_mass(sum(parts.values()), span_m=math.sqrt(gas["area"]) * 1.1)
                parts["structure"] = stm["mass_kg"]
                classes = {"intake": "new", "compressor": "new", "reservoir_feed": "existing", "ionizer": "new", "accelerator": "modified" if ac.family == "hall" else "new",
                           "neutralizer": "existing" if ne.name == "lab6_xe" else "new", "xe": "calculated", "xe_tank": "existing", "ppu": "modified", "thermal": "calculated", "structure": "calculated"}
                bom = build_bom(parts, classes)
                if dc.m_max_kg is not None and bom["mev_kg"] > dc.m_max_kg: rej("mass"); continue
                A_arr = sc.array_area_m2; m_arr = 0.0
                if size_arrays:                       # item 33: arrays sized to this candidate's power, their drag and mass counted
                    import copy as _copy
                    from .mission_env import array_area_for, ARRAY_AREAL_KG_M2
                    sc_c = _copy.copy(sc); A_arr = array_area_for(P_bus, sc, gas["alt"], P_cap_W=dc.P_bus_max_W); sc_c.array_area_m2 = A_arr
                    D_sc = spacecraft_drag(sc_c, atm["rho"], atm.get("V_rel", atm["V"]), gas["area"], gas["C_D"])["D_total_N"]
                    m_arr = A_arr * ARRAY_AREAL_KG_M2
                env_ok = True; T_lo = T_hi = None
                if mission_envelope:
                    # re-run this candidate's propulsion at solar-min and solar-max captured flow (density ratio, same
                    # reservoir conductance so p scales with flow); require closure with margin at both, power within cap
                    r_lo = atmosphere(gas["alt"], "low")["rho"] / atm["rho"]; r_hi = atmosphere(gas["alt"], "high")["rho"] / atm["rho"]
                    def _at(scale):
                        """Off-design point; the controller may retune source power (0.5-1.25x) to stay sustained and
                        maximise thrust within the bus cap — the same freedom for every plasma-fed architecture."""
                        g2 = dict(gas); g2["mdot_air"] = gas["mdot_air"] * scale; g2["p_in"] = gas["p_in"] * scale
                        best_q = (0.0, 0.0)
                        opts = [1.0] + ([0.5, 0.75, 1.25] if x.get("P_ion", 0.0) > 0 else [])
                        for f in opts:
                            x2 = dict(x)
                            if "P_ion" in x2: x2["P_ion"] = x["P_ion"] * f
                            try:
                                q = _propulsion(a, g2, x2)
                            except ValueError:
                                continue
                            Pq = (q["P_acc_W"] + q["P_ion_W"] + q["P_neut_W"] + P_mag + gas["comp_power"] + 5.0) / max(loads["eta_overall"], 0.5) + 12.0
                            Tq = q["T_N"] * (min(1.0, dc.P_bus_max_W / Pq) if Pq > 0 else 1.0)
                            if Tq > best_q[0]:
                                best_q = (Tq, min(Pq, dc.P_bus_max_W))
                        return best_q
                    T_lo, P_lo = _at(r_lo); T_hi, P_hi = _at(r_hi)       # power cap already applied inside _at
                    ratio_env = min(T / D_sc, T_lo / (D_sc * r_lo), T_hi / (D_sc * r_hi))
                    if best_env is None or ratio_env > best_env[0]:
                        best_env = (ratio_env, {"area": area, "p": p_level, **x, "T_mN": T * 1e3, "T_lo_mN": T_lo * 1e3, "T_hi_mN": T_hi * 1e3,
                                                "D_mN": D_sc * 1e3, "P_bus_W": P_bus, "MEV_kg": bom["mev_kg"]})
                    env_ok = ratio_env >= envelope_margin
                    if not env_ok:
                        rej("mission_envelope")
                        if keep_candidates:
                            cands.append({"architecture": name, "area": area, "p_res_Pa": p_level, **x, "T_mN": T * 1e3,
                                          "T_minus_D_mN": (T - D_sc) * 1e3, "T_over_D": T / D_sc, "env_ratio": ratio_env,
                                          "T_solar_min_mN": T_lo * 1e3, "T_solar_max_mN": T_hi * 1e3, "A_array_m2": A_arr,
                                          "m_array_kg": m_arr, "m_system_kg": bom["mev_kg"] + m_arr, "P_bus_W": P_bus,
                                          "MEV_kg": bom["mev_kg"], "life_h": life_sys, "xe_kg": xe_kg, "closes": False})
                        continue
                J = T - k_margin * D_sc
                cal, cal_x = calibration_status(ac.family, {"mdot_mgps": gas["mdot_air"] * 1e6, "Vd": x.get("Vd"), "P_W": pr["P_acc_W"],
                                                             "Isp_s": T / (G0 * max(gas["mdot_air"], 1e-12))})
                if keep_candidates:
                    cands.append({"architecture": name, "area": area, "p_res_Pa": p_level, **x, "J": J, "T_mN": T * 1e3, "T_minus_D_mN": (T - D_sc) * 1e3,
                                  "T_over_D": T / D_sc, "T_solar_min_mN": (T_lo or 0) * 1e3, "T_solar_max_mN": (T_hi or 0) * 1e3, "A_array_m2": A_arr, "m_array_kg": m_arr, "m_system_kg": bom["mev_kg"] + m_arr,
                                  "P_bus_W": P_bus, "MEV_kg": bom["mev_kg"], "life_h": life_sys, "xe_kg": xe_kg, "Q_W": sum(n.P_int_W for n in nodes),
                                  "calibration": cal, "extrapolation": cal_x, "ledger_resid": resid,
                                  "env_ratio": (min(T / D_sc, T_lo / (D_sc * r_lo), T_hi / (D_sc * r_hi)) if mission_envelope else T / D_sc),
                                  "closes": True})
                if dc.no_extrapolation and cal == "extrapolation": rej("extrapolation"); continue
                if dc.max_extrapolation is not None and cal != "uncalibrated" and cal_x > dc.max_extrapolation: rej("extrapolation"); continue
                if best is None or J > best["J"]:
                    if best is not None:
                        runners.append(best)
                    best = {"J": J, "x": x, "pr": pr, "ppu": ppu, "loads": loads, "P_bus": P_bus, "gas": gas, "D_sc": D_sc, "rad": rad,
                            "ledger": ledger, "resid": resid, "cal": cal, "cal_x": cal_x, "P_mag": P_mag, "A_arr": A_arr, "m_arr": m_arr,
                            "bom": bom, "life_items": life_items, "life_sys": life_sys, "xe_kg": xe_kg, "area": area, "p_level": p_level, "stm": stm}
    if best is None:
        status = "MODEL_ERROR" if (n_eval == 0 and n_model_err > 0) else "INFEASIBLE"
        return {"architecture": name, "valid": True, "feasible": False, "status": status, "family": ac.family,
                "reason": (f"model error: {last_err}" if status == "MODEL_ERROR" else "no candidate satisfies constraints: " + ", ".join(f"{k}={v}" for k, v in reject.items())),
                "n_eval": n_eval, "n_model_err": n_model_err,
                "best_envelope_ratio": best_env[0] if best_env else None, "best_envelope_point": best_env[1] if best_env else None,
                "_candidates": cands if keep_candidates else None}
    pr, x, ppu, loads, gas, D_sc, rad, bom = best["pr"], best["x"], best["ppu"], best["loads"], best["gas"], best["D_sc"], best["rad"], best["bom"]
    atm = atmosphere(gas["alt"], gas["solar"])
    rad = size_radiator(rad["_nodes"], ThermalParams(), atm["rho"], atm.get("V_rel", atm["V"]))   # full network on the winner
    tried = 0
    while not rad["feasible"] and runners and tried < 8:          # fall back to the next-best candidate
        tried += 1
        best = max(runners, key=lambda b: b["J"]); runners.remove(best)
        pr, x, ppu, loads, gas, D_sc, rad, bom = best["pr"], best["x"], best["ppu"], best["loads"], best["gas"], best["D_sc"], best["rad"], best["bom"]
        atm = atmosphere(gas["alt"], gas["solar"])
        rad = size_radiator(rad["_nodes"], ThermalParams(), atm["rho"], atm.get("V_rel", atm["V"]))
    if not rad["feasible"]:
        return {"architecture": name, "valid": True, "feasible": False, "status": "INFEASIBLE", "family": ac.family,
                "reason": "no candidate passes the full thermal network", "n_eval": n_eval}
    parts2 = {l.name: l.cbe_kg for l in bom["lines"]}; parts2["thermal"] = rad["m_thermal_kg"]
    bom = build_bom(parts2, {l.name: l.cls for l in bom["lines"]})
    T = pr["T_N"]; P_bus = best["P_bus"]; ne_ = ne
    at_edge = [k for k in keys if x[k] in (vars_[k][0], vars_[k][-1]) and len(vars_[k]) > 1]
    out = {"architecture": name, "valid": True, "feasible": True, "status": "OK", "family": ac.family, "n_eval": n_eval, "n_model_err": n_model_err,
           "x_area": best["area"], "x_p_level": best["p_level"], **{f"x_{k}": v for k, v in x.items()}, "optimum_at_search_edge": ",".join(at_edge),
           "T_mN": T * 1e3, "Isp_s": T / (G0 * max(gas["mdot_air"] + ne_.xe_mgps * 1e-6, 1e-12)),
           "P_ion_W": pr["P_ion_W"], "P_acc_W": pr["P_acc_W"], "P_neut_W": pr["P_neut_W"], "P_bus_W": P_bus, "ppu_eta": loads["eta_overall"],
           "chi_preion": pr["chi_preion"], "I_neut_req_A": pr["I_neut_req_A"], "I_neut_max_A": pr["I_neut_max_A"],
           "D_sc_mN": D_sc * 1e3, "T_over_D_sc": T / D_sc, "T_minus_kD_mN": (T - k_margin * D_sc) * 1e3,
           "Q_waste_W": rad["P_waste_W"], "A_rad_m2": rad["A_rad_m2"], "T_hot_limiting": rad["limiting_node"],
           "CBE_kg": bom["cbe_kg"], "MEV_kg": bom["mev_kg"], "xe_kg": best["xe_kg"], "life_sys_h": best["life_sys"],
           "life_limiting": min(best["life_items"], key=best["life_items"].get), "structure_first_mode_Hz": best["stm"]["first_mode_Hz"],
           "mdot_air_mgps": gas["mdot_air"] * 1e6, "p_in_Pa": gas["p_in"], "eta_c": gas["eta_c"], "C_D": gas["C_D"], "atmosphere": gas["atmosphere"],
           "bus_area_m2": sc.bus_frontal_m2, "array_area_m2": sc.array_area_m2, "pointing_deg": sc.pointing_sigma_deg,
           "rejections": ";".join(f"{k}={v}" for k, v in reject.items()),
           "P_jet_W": best["ledger"]["jet"], "ledger_resid": best["resid"], "calibration": best["cal"], "extrapolation": best["cal_x"],
           "firing_hours_for_xe": firing_hours, "_candidates": cands if keep_candidates else None,
           "A_array_m2": best["A_arr"], "m_array_kg": best["m_arr"], "m_system_kg": bom["mev_kg"] + best["m_arr"],
           **{k: pr[k] for k in ("eta_b", "Te_eV", "sustained", "onset", "space_charge_limited", "eta_pit", "T0_K", "kind") if k in pr}}
    out["thrust_min_ok"] = (dc.T_min_mN is None) or (T * 1e3 >= dc.T_min_mN)
    out["thrust_max_ok"] = (dc.T_max_mN is None) or (T * 1e3 <= dc.T_max_mN)
    out["mass_ok"] = (dc.m_max_kg is None) or (bom["mev_kg"] <= dc.m_max_kg)
    out["life_ok"] = (dc.life_min_h is None) or (best["life_sys"] >= dc.life_min_h)
    out["all_constraints_ok"] = out["thrust_min_ok"] and out["thrust_max_ok"] and out["mass_ok"] and out["life_ok"]
    # degeneracy of the optimum: candidates within 1 % of the best objective (a small input change can flip the argmax)
    Js = [c["J"] for c in cands if c.get("closes", True) and "J" in c]
    if Js:
        J1 = max(Js); tol = 0.01 * max(abs(J1), 1e-6)
        out["near_tie_count"] = int(sum(1 for j in Js if J1 - j <= tol))
        out["optimum_degenerate"] = out["near_tie_count"] > 1
    out["_design"] = {"a": a, "x": dict(x), "area": best["area"], "p_level": best["p_level"], "eta_ppu": loads["eta_overall"],
                      "P_mag": best["P_mag"], "comp_power": gas["comp_power"]}
    return out


def propulsion_map(result: dict, gas_fn, scales=(0.3, 0.45, 0.6, 0.75, 0.9, 1.0, 1.15, 1.3, 1.5)) -> dict:
    """Item 15: re-run the propulsion physics of the *winning design* at scaled captured flow (reservoir pressure
    scales with flow at fixed conductance), so the mission sees ignition loss, utilisation changes and power
    nonlinearly instead of T ∝ mdot. Returns arrays for interpolation in the mission loop."""
    d = result["_design"]; a = d["a"]; x = d["x"]
    gas0 = gas_fn(d["area"], d["p_level"])
    T = []; P = []
    HALL_OVERRIDES["start"] = "hot"          # a running thruster stays on its branch (continuation) while the branch exists
    for s in scales:
        gas = dict(gas0); gas["mdot_air"] = gas0["mdot_air"] * s; gas["p_in"] = gas0["p_in"] * s
        try:
            pr = _propulsion(a, gas, x)
            T_s = pr["T_N"]
            P_dev = pr["P_acc_W"] + pr["P_ion_W"] + pr["P_neut_W"] + d["P_mag"] + d["comp_power"] + 5.0
        except ValueError:
            T_s = 0.0
            P_dev = d["P_mag"] + d["comp_power"] + 5.0 + 45.0          # dark channel: keeper/cathode + compressor
        T.append(T_s); P.append(P_dev / max(d["eta_ppu"], 0.5) + 12.0)
    HALL_OVERRIDES.pop("start", None)
    return {"scale": list(scales), "T_N": T, "P_bus_W": P, "mdot0": gas0["mdot_air"]}


def pareto_front(cands: list[dict]) -> "pd.DataFrame":
    """Non-dominated set in (max T-D, min P_bus, min MEV, max life, min Xe) — item 36 (no single weighted objective)."""
    import numpy as np
    df = pd.DataFrame(cands)
    if df.empty:
        return df
    msys = df.m_system_kg if "m_system_kg" in df else df.MEV_kg
    lead = -df.env_ratio if "env_ratio" in df else -df.T_minus_D_mN
    obj = np.column_stack([lead, df.P_bus_W, msys, -df.life_h, df.xe_kg])
    nd = np.ones(len(df), bool)
    for i in range(len(df)):
        dominated = np.all(obj <= obj[i], axis=1) & np.any(obj < obj[i], axis=1)
        if dominated.any():
            nd[i] = False
    df["pareto"] = nd
    return df


def dedupe_designs(df: "pd.DataFrame", keys=("architecture", "area", "P_ion", "Vd", "L_ch", "Vb", "P_acc", "E_pulse")) -> "pd.DataFrame":
    """Collapse candidates that differ only in variables with no effect on the outcome (e.g. reservoir pressure for
    a self-ionising Hall), keeping the first occurrence; reports how many were merged."""
    k = [c for c in keys if c in df.columns]
    out = df.drop_duplicates(subset=k + ["T_mN", "P_bus_W"]).copy()
    out.attrs["merged"] = len(df) - len(out)
    return out


_GAS_CACHE: dict = {}


def make_gas_fn(alpha=0.8, L_over_d=5, alt=200, solar="mean", blade_coating_um=50.0):
    """Gas-path variables for the nested search: intake area and reservoir pressure level
    (nominal = 3 x p_min of a Hall; 'low' = 1.5 x; 'high' = 6 x) — item 9."""
    def fn(area, p_level):
        """p_level: absolute reservoir pressure in Pa (architecture-neutral), or a legacy label."""
        key = (round(area, 3), p_level, alpha, L_over_d, alt, solar)
        if key not in _GAS_CACHE:
            if isinstance(p_level, str):
                _GAS_CACHE[key] = gas_path_state(area, alpha, L_over_d, alt, solar, blade_coating_um,
                                                 p_margin={"low": 1.5, "nominal": 3.0, "high": 6.0}[p_level])
            else:
                _GAS_CACHE[key] = gas_path_state(area, alpha, L_over_d, alt, solar, blade_coating_um, p_target=float(p_level))
        return _GAS_CACHE[key]
    return fn


def run_all(gas_fn, sc, dc: DesignConstraints | None = None, k_margin: float = 1.3, gas_vars: dict | None = None,
            strict: bool = False, archs=None) -> pd.DataFrame:
    rows = []
    for a in (archs or enumerate_architectures()):
        rows.append(close_architecture(a, gas_fn, sc, dc, k_margin, gas_vars, strict))
    return pd.DataFrame(rows)


def gas_path_state(area_m2=0.7, alpha=0.8, L_over_d=5, alt=200, solar="mean", blade_coating_um=50.0, p_margin=3.0,
                   p_target: float | None = None) -> dict:
    """Run Phases 1-2 (+ intake/blade life) once; the spacecraft is passed separately to run_all (item 26)."""
    from .system import Config, evaluate
    from .intake import IntakeParams, CompressorParams
    from .life import LifeInputs, blade_life, intake_life
    r = evaluate(Config("hall_1stage", alt, solar, IntakeParams(area_m2=area_m2, accommodation=alpha, use_tpmc=True, L_over_d=L_over_d),
                        CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, p_margin_over_pmin=p_margin, p_target_Pa=p_target))
    li = LifeInputs(blade_coating_um=blade_coating_um, blade_tip_mps=r.get("comp_tip_mps", 400.0), ao_flux_ram_m2_s=r["ao_flux_m2s"], intake_alpha0=alpha)
    return {"mdot_air": r["mdot_air_mgps"] * 1e-6, "p_in": r["p_in_Pa"], "fO": r["fO_inlet"], "fN2": 1 - r["fO_inlet"] - r["fO2_inlet"],
            "fO2": r["fO2_inlet"], "comp_power": r["P_comp_W"], "comp_mass": r["m_comp_kg"], "intake_mass": r["m_intake_kg"],
            "eta_c": r["eta_c"], "C_D": r["C_D"], "area": area_m2, "ao_flux": r["ao_flux_m2s"], "alt": alt, "solar": solar,
            "blade_life_h": blade_life(li)["coating_life_h"], "intake_life_h": 1e6 if intake_life(li)["coating_ok"] else 5000.0,
            "atmosphere": r["atm_source"]}
