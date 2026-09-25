"""Species-resolved reservoir / feed network with wall chemistry (Phase 2, items 7 and 8).

State: mass inventory m_s of O, O2, N2 (kg) in a reservoir of volume V at temperature T with walls of
area A_w and material M. Molecular-flow conductances (∝ c_bar_s) to the anode, and a leak path.

  dm_s/dt = mdot_in,s - n_s C_anode,s m_s - n_s C_leak,s m_s + R_s
  R_O   = - gamma_O(T) * (n_O c_bar_O / 4) * A_w * m_O           (O lost to wall recombination)
  R_O2  = + (same mass gain)                                       (mass-conserving)
  n_s   = m_s / (m_mol,s V),  p_s = n_s k T

Steady state is solved by damped fixed-point iteration (the system is linear in n_s except through
recombination, which is linear too — so this converges quickly). Outputs: p_total, composition at the
anode, O survival, residence time, wall collisions per molecule, and the number of wall collisions the
compressor stages contribute (passed in), so the "gamma^N" shortcut is replaced by a real balance.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .constants import K_B, M_SPECIES
from .materials import DB


@dataclass
class Reservoir:
    volume_m3: float = 2.0e-3      # 2 litres
    wall_area_m2: float = 0.12
    wall_material: str = "Ti6Al4V"
    T_K: float = 350.0
    anode_orifice_area_m2: float = 8.0e-6     # effective orifice/feed area to the thruster anode
    anode_orifice_K: float = 0.6              # Clausing factor of the feed path
    leak_area_m2: float = 5.0e-8
    # upstream stages (compressor internals) also recombine: give their wall-collision count and material
    upstream_collisions: float = 60.0
    upstream_material: str = "Ti6Al4V"

    def _cbar(self, s):
        return math.sqrt(8 * K_B * self.T_K / (math.pi * M_SPECIES[s]))

    def conductance(self, s, area, K=1.0):
        """Molecular-flow orifice conductance [m^3/s] = K * A * c_bar / 4."""
        return K * area * self._cbar(s) / 4.0

    def steady_state(self, mdot_in: dict) -> dict:
        # upstream (compressor channel) recombination first: O survival through N collisions at gamma(T)
        g_up = DB[self.upstream_material].gamma_O(self.T_K)
        surv_up = (1.0 - g_up) ** self.upstream_collisions
        m_in = dict(mdot_in)
        lost = m_in.get("O", 0.0) * (1.0 - surv_up)
        m_in["O"] = m_in.get("O", 0.0) * surv_up
        m_in["O2"] = m_in.get("O2", 0.0) + lost
        gam = DB[self.wall_material].gamma_O(self.T_K)
        species = ("O", "O2", "N2")
        n = {s: 1e14 for s in species}
        C = {s: self.conductance(s, self.anode_orifice_area_m2, self.anode_orifice_K) + self.conductance(s, self.leak_area_m2)
             for s in species}
        for _ in range(200):
            new = {}
            k_rec = gam * (self._cbar("O") / 4.0) * self.wall_area_m2          # 1/s per unit n_O * V ... (mass rate = k n_O m_O)
            # O balance: mdot_in,O = n_O C_O m_O + k_rec n_O m_O
            new["O"] = m_in["O"] / (M_SPECIES["O"] * (C["O"] + k_rec)) if (C["O"] + k_rec) > 0 else 0.0
            rec_mass = k_rec * new["O"] * M_SPECIES["O"]
            new["O2"] = (m_in["O2"] + rec_mass) / (M_SPECIES["O2"] * C["O2"])
            new["N2"] = m_in["N2"] / (M_SPECIES["N2"] * C["N2"])
            if all(abs(new[s] - n[s]) <= 1e-6 * max(new[s], 1e-30) for s in species):
                n = new; break
            n = {s: 0.5 * (n[s] + new[s]) for s in species}
        p = {s: n[s] * K_B * self.T_K for s in species}
        p_tot = sum(p.values())
        out = {s: n[s] * C[s] * M_SPECIES[s] for s in species}   # mass flow to anode+leak
        anode = {s: n[s] * self.conductance(s, self.anode_orifice_area_m2, self.anode_orifice_K) * M_SPECIES[s] for s in species}
        mtot_out = sum(anode.values())
        N_tot = sum(n.values())
        tau = (sum(n[s] * M_SPECIES[s] for s in species) * self.volume_m3) / max(sum(out.values()), 1e-30)
        coll = tau * (self._cbar("O") / 4.0) * self.wall_area_m2 / self.volume_m3
        O_in_total = mdot_in.get("O", 0.0)
        return {"p_total_Pa": p_tot, "p_species_Pa": p, "n_species": n, "T_K": self.T_K,
                "mdot_anode": anode, "mdot_leak": {s: out[s] - anode[s] for s in species},
                "composition_anode_mass": {s: anode[s] / mtot_out for s in species} if mtot_out > 0 else {},
                "O_survival": (anode["O"] / O_in_total) if O_in_total > 0 else 0.0,
                "residence_time_s": tau, "wall_collisions_reservoir": coll, "gamma_wall": gam, "gamma_upstream": g_up,
                "upstream_survival": surv_up, "volume_m3": self.volume_m3, "wall_area_m2": self.wall_area_m2}


def size_orifice_for_pressure(res: Reservoir, mdot_in: dict, p_target_Pa: float) -> float:
    """Anode feed area that puts the reservoir at p_target for the given inflow (bisection)."""
    lo, hi = 1e-8, 3e-2      # up to 300 cm^2: at 0.1 Pa, 1 mg/s is ~1.5 m^3/s, so the "orifice" is the thruster channel itself
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        res.anode_orifice_area_m2 = mid
        p = res.steady_state(mdot_in)["p_total_Pa"]
        if p > p_target_Pa:
            lo = mid
        else:
            hi = mid
    return res.anode_orifice_area_m2



def startup_transient(res: Reservoir, mdot_captured: dict, p_ignite_Pa: float, spinup_s: float = 60.0,
                      t_end_s: float = 600.0, dt_s: float = 0.05) -> dict:
    """Species-resolved reservoir inventory during compressor spin-up (document 16, item 16):
        dm_s/dt = f(t) * mdot_in,s - n_s C_s m_s + R_s,   n_s = m_s / (m_mol V),  R_O = -gamma(T) (c_bar/4) A_w n_O m_O
    with f(t) = min(t/spinup, 1) the delivered fraction while the rotor accelerates. Returns time to reach the
    ignition pressure, steady pressure, and the time constant V/C (explicit integration; tau >> dt)."""
    import numpy as np
    species = ("O", "O2", "N2")
    m = {s: 0.0 for s in species}
    C = {s: res.conductance(s, res.anode_orifice_area_m2, res.anode_orifice_K) + res.conductance(s, res.leak_area_m2) for s in species}
    gam = DB[res.wall_material].gamma_O(res.T_K)
    k_rec = gam * (res._cbar("O") / 4.0) * res.wall_area_m2 / res.volume_m3          # 1/s on n_O
    t = 0.0; t_ign = None; hist = []
    tau = res.volume_m3 / min(C.values())
    dt = min(dt_s, tau / 20.0)
    while t < t_end_s:
        f = min(t / spinup_s, 1.0) if spinup_s > 0 else 1.0
        dm = {}
        rec = k_rec * m["O"]
        for s_ in species:
            out = C[s_] / res.volume_m3 * m[s_]
            dm[s_] = f * mdot_captured.get(s_, 0.0) - out
        dm["O"] -= rec; dm["O2"] += rec
        for s_ in species:
            m[s_] = max(m[s_] + dm[s_] * dt, 0.0)
        p = sum(m[s_] / (M_SPECIES[s_] * res.volume_m3) for s_ in species) * K_B * res.T_K
        if t_ign is None and p >= p_ignite_Pa:
            t_ign = t
        if len(hist) == 0 or t - hist[-1][0] >= t_end_s / 200:
            hist.append((t, p))
        t += dt
    return {"t_ignite_s": t_ign, "p_final_Pa": p, "tau_s": tau, "history": np.array(hist)}
