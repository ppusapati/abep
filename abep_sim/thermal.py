"""Lumped thermal network (Phase 4, items 24, 25).

Nodes: intake, compressor, thruster (channel + anode + magnets), stage1 source, cathode, PPU, radiator.
Each node: internal dissipation, conductive links to the radiator/structure, radiative coupling to space.
External loads: solar (1361 W/m2 * absorptivity * view factor * sun fraction), Earth IR (~237 W/m2), albedo,
ram-face aerodynamic heating (rho V^3 / 2 * accommodation on the ram area — real at 180 km, W/m2 class).
Steady state solved for sunlit and eclipse cases; radiator area sized so that every node stays under its limit
in the hot case; radiator mass from areal density (panel + heat pipes/straps).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np

SIGMA = 5.670374419e-8
SOLAR = 1361.0
EARTH_IR = 237.0
ALBEDO = 0.3


@dataclass
class Node:
    name: str
    P_int_W: float                 # internal dissipation
    T_max_K: float
    area_ext_m2: float = 0.0       # external radiating/absorbing area
    emissivity: float = 0.85
    absorptivity: float = 0.3
    sun_view: float = 0.5          # fraction of external area seeing the sun when sunlit
    earth_view: float = 0.3
    ram_view: float = 0.0          # fraction of area on the ram face (aero heating)
    G_to_rad_W_K: float = 1.0      # conductance to radiator node
    mCp_J_K: float = 2000.0


@dataclass
class ThermalParams:
    radiator_areal_kg_m2: float = 4.0     # panel + heat pipes/straps + coating
    radiator_emissivity: float = 0.88
    radiator_absorptivity: float = 0.15   # OSR / white paint
    radiator_sun_view: float = 0.2
    radiator_earth_view: float = 0.4
    radiator_T_max_K: float = 330.0
    sunlit_fraction: float = 0.62         # 200 km, ~40 % eclipse
    aero_accommodation: float = 0.8


def aero_heating_W_m2(rho: float, V: float, accommodation: float) -> float:
    return 0.5 * rho * V ** 3 * accommodation


def solve_network(nodes: list[Node], tp: ThermalParams, A_rad_m2: float, rho: float, V: float, sunlit: bool) -> dict:
    """Steady state: for each node,  P_int + P_ext - eps sigma A (T^4 - T_space^4) - G (T - T_rad) = 0 ;
    radiator: sum G (T_i - T_rad) + P_ext,rad - eps_r sigma A_r T_rad^4 = 0. Newton iteration on T."""
    n = len(nodes)
    T = np.full(n + 1, 300.0)
    q_aero = aero_heating_W_m2(rho, V, tp.aero_accommodation)
    for _ in range(200):
        Tr = T[-1]
        # radiator external load
        P_ext_r = A_rad_m2 * (tp.radiator_absorptivity * SOLAR * tp.radiator_sun_view * (1 if sunlit else 0)
                              + tp.radiator_emissivity * EARTH_IR * tp.radiator_earth_view
                              + tp.radiator_absorptivity * ALBEDO * SOLAR * tp.radiator_earth_view * (1 if sunlit else 0))
        res = np.zeros(n + 1); jac = np.zeros((n + 1, n + 1))
        for i, nd in enumerate(nodes):
            Ti = T[i]
            P_ext = nd.area_ext_m2 * (nd.absorptivity * SOLAR * nd.sun_view * (1 if sunlit else 0)
                                      + nd.emissivity * EARTH_IR * nd.earth_view
                                      + nd.absorptivity * ALBEDO * SOLAR * nd.earth_view * (1 if sunlit else 0)
                                      + q_aero * nd.ram_view)
            rad = nd.emissivity * SIGMA * nd.area_ext_m2 * (Ti ** 4 - 4.0 ** 4)
            res[i] = nd.P_int_W + P_ext - rad - nd.G_to_rad_W_K * (Ti - Tr)
            jac[i, i] = -4 * nd.emissivity * SIGMA * nd.area_ext_m2 * Ti ** 3 - nd.G_to_rad_W_K
            jac[i, -1] = nd.G_to_rad_W_K
        res[-1] = sum(nd.G_to_rad_W_K * (T[i] - Tr) for i, nd in enumerate(nodes)) + P_ext_r - tp.radiator_emissivity * SIGMA * A_rad_m2 * (Tr ** 4 - 4.0 ** 4)
        for i, nd in enumerate(nodes):
            jac[-1, i] = nd.G_to_rad_W_K
        jac[-1, -1] = -sum(nd.G_to_rad_W_K for nd in nodes) - 4 * tp.radiator_emissivity * SIGMA * A_rad_m2 * Tr ** 3
        dT = np.linalg.solve(jac, -res)
        T = T + np.clip(dT, -80, 80)
        if np.max(np.abs(dT)) < 1e-3:
            break
    return {"T": {nd.name: float(T[i]) for i, nd in enumerate(nodes)}, "T_radiator": float(T[-1]),
            "q_aero_W_m2": q_aero, "sunlit": sunlit}


STRAP_KG_PER_W_K = 0.025   # heat pipe / strap mass per W/K of conductance


def size_straps(nodes: list[Node], tp: ThermalParams, margin: float = 1.3) -> float:
    """Heat-path conductance is a design variable: raise each node's conductance to the radiator so its
    dissipation crosses (T_max - T_rad,max) with margin. Returns the added strap mass."""
    added = 0.0
    for nd in nodes:
        dT = max(nd.T_max_K - tp.radiator_T_max_K, 5.0)
        G_need = margin * nd.P_int_W / dT
        if G_need > nd.G_to_rad_W_K:
            added += (G_need - nd.G_to_rad_W_K) * STRAP_KG_PER_W_K
            nd.G_to_rad_W_K = G_need
    return added


def size_radiator(nodes: list[Node], tp: ThermalParams, rho: float, V: float) -> dict:
    """Smallest radiator area such that all nodes and the radiator are under limits in the sunlit (hot) case.
    Strap conductances are sized first (their mass is included)."""
    m_straps = size_straps(nodes, tp)
    lo, hi = 0.01, 5.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        hot = solve_network(nodes, tp, mid, rho, V, True)
        ok = hot["T_radiator"] <= tp.radiator_T_max_K and all(hot["T"][nd.name] <= nd.T_max_K for nd in nodes)
        if ok:
            hi = mid
        else:
            lo = mid
    A = hi
    hot = solve_network(nodes, tp, A, rho, V, True)
    cold = solve_network(nodes, tp, A, rho, V, False)
    limiting = max(nodes, key=lambda nd: hot["T"][nd.name] / nd.T_max_K).name
    return {"A_rad_m2": A, "m_thermal_kg": A * tp.radiator_areal_kg_m2 + 0.4 * len(nodes) * 0.15 + m_straps, "m_straps_kg": m_straps,
            "hot": hot, "cold": cold, "limiting_node": limiting,
            "P_waste_W": sum(nd.P_int_W for nd in nodes), "feasible": A < 4.9}


def default_nodes(P_d_W: float, I_beam_A: float, Vd: float, P_s1_dc_W: float, eta_s1: float, P_comp_W: float,
                  P_cath_W: float, P_ppu_loss_W: float, A_intake_m2: float, A_thruster_ext_m2: float = 0.03) -> list[Node]:
    """Dissipation split: thruster waste = P_d - beam kinetic power (beam power leaves with the plume)."""
    P_beam = I_beam_A * Vd * 0.85
    P_thr_waste = max(P_d_W - P_beam, 0.0) * 0.6      # ~40 % of the non-beam power leaves as plasma/plume radiation
    return [
        Node("intake", 0.0, 450.0, area_ext_m2=A_intake_m2 * 1.6, emissivity=0.8, absorptivity=0.3, sun_view=0.3, earth_view=0.3, ram_view=1.0 / 1.6, G_to_rad_W_K=0.5, mCp_J_K=4000),
        Node("compressor", P_comp_W, 400.0, area_ext_m2=0.15, emissivity=0.8, absorptivity=0.3, G_to_rad_W_K=1.5, mCp_J_K=6000),
        Node("thruster", P_thr_waste, 620.0, area_ext_m2=A_thruster_ext_m2, emissivity=0.85, absorptivity=0.4, sun_view=0.2, G_to_rad_W_K=0.8, mCp_J_K=4000),
        Node("magnets", P_thr_waste * 0.15, 520.0, area_ext_m2=0.01, G_to_rad_W_K=1.2, mCp_J_K=1500),
        Node("stage1_source", P_s1_dc_W * (1 - eta_s1), 360.0, area_ext_m2=0.02, G_to_rad_W_K=2.0, mCp_J_K=1500),
        Node("cathode", P_cath_W * 0.5, 800.0, area_ext_m2=0.004, G_to_rad_W_K=0.3, mCp_J_K=300),
        Node("ppu", P_ppu_loss_W, 340.0, area_ext_m2=0.06, emissivity=0.85, absorptivity=0.25, sun_view=0.1, G_to_rad_W_K=6.0, mCp_J_K=6000),
    ]
