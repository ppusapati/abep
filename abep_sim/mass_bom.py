"""Hierarchical mass properties (Phase 4, items 30, 31, 32).

Every line: CBE from geometry/physics, MGA by item class, MEV = CBE*(1+MGA). Tanks from pressure-vessel sizing,
Hall magnetic circuit from required flux, structure from launch loads (quasi-static + first-mode stiffness),
thermal from thermal.py, PPU from ppu.py, intake/compressor from Phases 1-2. Also centre of mass / inertia
about the thrust axis for the propulsion assembly (rough, for AOCS interface).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from .materials import DB

MU0 = 4e-7 * math.pi
MGA = {"new": 0.30, "modified": 0.15, "existing": 0.05, "calculated": 0.10}


def xe_tank(m_xe_kg: float, p_MPa: float = 15.0, material: str = "Ti6Al4V", safety: float = 2.0, rho_xe_kg_m3: float = 1600.0) -> dict:
    """Spherical tank: t = p r / (2 sigma_allow); mass = 4 pi r^2 t rho + fittings. Minimum gauge 0.8 mm."""
    V = m_xe_kg / rho_xe_kg_m3 * 1.05
    r = (3 * V / (4 * math.pi)) ** (1 / 3)
    m = DB[material]
    t = max(p_MPa * 1e6 * r / (2 * m.yield_MPa * 1e6 / safety), 0.8e-3)
    mass = 4 * math.pi * r ** 2 * t * m.density + 0.35
    return {"V_L": V * 1e3, "r_mm": r * 1e3, "t_mm": t * 1e3, "mass_kg": mass, "material": material}


def reservoir_vessel(V_m3: float, material: str = "Al6061") -> dict:
    """Low-pressure vessel: minimum gauge dominates (p << 1 kPa)."""
    r = (3 * V_m3 / (4 * math.pi)) ** (1 / 3)
    m = DB[material]; t = 1.0e-3
    return {"mass_kg": 4 * math.pi * r ** 2 * t * m.density + 0.25, "t_mm": t * 1e3}


def hall_magnetic_circuit(B_gap_T: float, r_in: float, r_out: float, L: float, material: str = "SmCo_bare",
                          H_op_A_m: float = 4.0e5, leakage: float = 3.0, yoke_t_m: float = 0.004, iron_rho: float = 7800.0) -> dict:
    """Permanent-magnet circuit sized by MMF and flux: magnet length l_m = leakage * B_gap * gap / (mu0 * H_op),
    magnet area = flux / B_m (B_m ~ 0.8 T at the operating point), for inner and outer magnet rings;
    soft-iron yoke: cylindrical shell around the channel + two end plates + inner core."""
    gap = r_out - r_in
    l_m = leakage * B_gap_T * gap / (MU0 * H_op_A_m)
    flux = B_gap_T * 2 * math.pi * 0.5 * (r_in + r_out) * L * 0.5     # radial flux across half the channel length
    A_m = leakage * flux / 0.8
    V_mag = 2 * l_m * A_m                                              # inner + outer rings
    m_mag = V_mag * DB[material].density
    r_y = r_out + 0.015
    m_shell = 2 * math.pi * r_y * L * yoke_t_m * iron_rho
    m_plates = 2 * math.pi * (r_y ** 2) * yoke_t_m * iron_rho
    m_core = math.pi * (r_in - 0.004) ** 2 * L * iron_rho * 0.5
    return {"m_magnets_kg": m_mag, "m_poles_kg": m_shell + m_plates + m_core, "mass_kg": m_mag + m_shell + m_plates + m_core,
            "l_m_mm": l_m * 1e3}


def hall_channel_mass(r_in, r_out, L, t_wall_mm=4.0, material="BN") -> float:
    m = DB[material]
    A = 2 * math.pi * (r_in + r_out) * L
    return A * t_wall_mm * 1e-3 * m.density + 0.3     # + anode/gas distributor


def structure_mass(m_supported_kg: float, span_m: float, g_qs: float = 12.0, f_min_Hz: float = 60.0,
                   material: str = "Al6061", core_h_m: float = 0.025, core_rho: float = 50.0) -> dict:
    """Secondary structure of the propulsion module: aluminium-faced honeycomb sandwich deck (span x span) sized by
    first-mode stiffness (distributed mass, simply supported: f = (pi/2L^2) sqrt(D/(m/A)) ) and by quasi-static
    bending at g_qs; plus intake support frame and brackets."""
    m = DB[material]
    E = m.E_GPa * 1e9
    A = span_m * span_m
    # sandwich bending stiffness per unit width D = E t_f h^2 / 2 ; mass per area mu = 2 t_f rho + core
    t_f = 0.3e-3
    for _ in range(60):
        D = E * t_f * core_h_m ** 2 / 2.0
        mu = 2 * t_f * m.density + core_h_m * core_rho + m_supported_kg / A
        f = (math.pi / (2 * span_m ** 2)) * math.sqrt(D / mu)
        F = m_supported_kg * 9.81 * g_qs
        sigma = (F * span_m / 8) / (t_f * core_h_m * span_m)        # face-sheet stress, sandwich
        if f >= f_min_Hz and sigma < m.yield_MPa * 1e6 / 1.5:
            break
        t_f *= 1.1
    mass_deck = A * (2 * t_f * m.density + core_h_m * core_rho)
    frame = 0.10 * m_supported_kg + 1.5 * span_m                     # brackets, inserts, struts, intake frame
    # The mounting deck is spacecraft-provided (DRDO bus); the propulsion module carries only its frame/brackets.
    return {"panel_t_mm": t_f * 1e3, "core_mm": core_h_m * 1e3, "mass_kg": frame, "deck_if_own_kg": mass_deck,
            "first_mode_Hz": f, "sigma_MPa": sigma / 1e6}


@dataclass
class BOMLine:
    name: str
    cbe_kg: float
    cls: str
    note: str = ""

    @property
    def mga(self):
        return MGA[self.cls]

    @property
    def mev_kg(self):
        return self.cbe_kg * (1 + self.mga)


def build_bom(parts: dict, classes: dict, notes: dict | None = None) -> dict:
    lines = [BOMLine(k, v, classes.get(k, "new"), (notes or {}).get(k, "")) for k, v in parts.items()]
    cbe = sum(l.cbe_kg for l in lines); mev = sum(l.mev_kg for l in lines)
    return {"lines": lines, "cbe_kg": cbe, "mev_kg": mev, "mga_kg": mev - cbe,
            "table": [(l.name, round(l.cbe_kg, 2), l.cls, round(l.mev_kg, 2), l.note) for l in lines]}
