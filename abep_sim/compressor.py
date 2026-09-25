"""Molecular-drag compressor physics (Phase 2, item 6).

Holweck/Gaede-type drag stages in the free-molecular regime. Per stage of channel depth h, length L,
width w, with rotor tangential speed u and gas mean thermal speed c_bar(species):

  zero-flow compression        ln K0_s = 2 u L / (c_bar_s h) * xi          (xi = geometric efficiency, ~0.5-0.8)
  pumping speed (zero pressure) S0    = xi * u * h * w / 2                 [m^3/s]
  throughput relation          K_s = K0_s - (K0_s - 1) * Q_s / (S0 * p_in,s)   (linear Gaede characteristic)
  stages cascade: p_out = p_in * prod K_s(stage), with Q constant through the machine (no leak) or reduced by
  leakage L_leak = C_leak * (p_out - p_in)

Because c_bar ∝ 1/sqrt(m), heavy species (O2, N2) are compressed more than O -> the reservoir is O-depleted
relative to the intake even before wall recombination. Power:
  gas drag torque:   tau_gas = sum_channels p_ch * (u / c_bar) * A_wet * 2/sqrt(pi)   (free-molecular shear)
  bearings:          P_bear = k_bear * omega                                    (magnetic ~ 1-3 W, ball ~ 5-15 W)
  motor:             P_el = (P_gas + P_bear) / eta_motor + P_ctrl
Rotor stress: sigma_hoop ~ rho_rotor u^2  ->  u_max = sqrt(sigma_allow / rho)   (Al ~ 320 m/s, Ti ~ 450, CFRP ~ 600)
Mass: rotor (disc + channels), stator, motor (mass ∝ torque), bearings, housing.
Temperature: lumped node, P_loss vs radiative+conductive sink.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .constants import K_B, M_SPECIES
from .materials import DB


@dataclass
class DragCompressor:
    # --- first stage: turbomolecular rotor spanning the intake throat (needed because at 0.01 Pa, 1 mg/s is ~10 m^3/s)
    turbo_rows: int = 3            # blade rows (rotor/stator pairs)
    turbo_area_m2: float = 0.25    # swept annulus area (≈ intake throat)
    turbo_radius_m: float = 0.30
    turbo_kS: float = 0.20         # pumping-speed coefficient S = kS * u * A   (0.15-0.3 for open-blade rows)
    turbo_kK: float = 1.2          # ln K0 = kK * u / c_bar per row
    turbo_blade_area_frac: float = 0.35
    turbo_disc_thickness_m: float = 0.002
    # --- drag (Holweck) stages after the turbo stage
    n_stages: int = 4
    rotor_radius_m: float = 0.06
    rpm: float = 60000.0
    h_mm: float = 3.0              # channel depth
    w_mm: float = 12.0             # channel width
    L_per_stage_m: float = 0.35    # unwrapped channel length per stage
    xi: float = 0.6                # geometric efficiency of drag channel
    rotor_material: str = "Ti6Al4V"
    stress_safety: float = 2.0
    T_gas_K: float = 350.0
    leak_conductance_m3_s: float = 2e-4
    k_bear_W_per_rads: float = 3e-4   # magnetic bearings
    eta_motor: float = 0.80
    P_ctrl_W: float = 8.0
    rotor_disc_thickness_m: float = 0.004
    stator_mass_factor: float = 1.2  # stator + housing relative to rotor
    motor_kg_per_Nm: float = 4.0
    bearing_kg: float = 0.6
    conductance_to_sink_W_K: float = 0.4
    T_sink_K: float = 293.0

    @property
    def u(self) -> float:
        return self.rotor_radius_m * self.rpm * 2 * math.pi / 60.0

    def u_max(self) -> float:
        m = DB[self.rotor_material]
        return math.sqrt(m.yield_MPa * 1e6 / (self.stress_safety * m.density))

    def _cbar(self, m):
        return math.sqrt(8 * K_B * self.T_gas_K / (math.pi * m))

    def run(self, p_in_Pa: float, mdot_species: dict, self_consistent: bool = True) -> dict:
        """Operating point with leakage solved self-consistently (document 16, item 13): the leak path returns gas
        from the outlet to the inlet, so the machine's throughput is (captured + recirculated). Iterate
        Q_through = Q_captured + Q_leak(p_out(Q_through)) to a fixed point; delivered = captured (steady state:
        everything captured eventually leaves through the outlet), but p_out and CR are those at the higher throughput."""
        if not self_consistent:
            return self._run_once(p_in_Pa, mdot_species)
        recirc = {s: 0.0 for s in mdot_species}
        r = None
        for _ in range(40):
            through = {s: mdot_species[s] + recirc[s] for s in mdot_species}
            r = self._run_once(p_in_Pa, through)
            new = {s: max(r["leak_kgps"][s], 0.0) for s in mdot_species}
            if all(abs(new[s] - recirc[s]) <= 1e-4 * max(mdot_species[s], 1e-15) for s in mdot_species):
                recirc = new; break
            recirc = {s: 0.5 * (recirc[s] + new[s]) for s in mdot_species}
        r["recirculated_kgps"] = recirc
        r["recirculation_frac"] = sum(recirc.values()) / max(sum(mdot_species.values()), 1e-30)
        r["delivered_kgps"] = dict(mdot_species)          # steady state: outflow = captured inflow
        r["leak_kgps"] = recirc
        return r

    def _run_once(self, p_in_Pa: float, mdot_species: dict) -> dict:
        """mdot_species: {species: kg/s} through the machine at inlet pressure p_in (partial pressures ∝ number flow)."""
        u = self.u
        h = self.h_mm * 1e-3; w = self.w_mm * 1e-3; L = self.L_per_stage_m
        S0 = self.xi * u * h * w / 2.0
        # inlet partial pressures from mole fractions
        nflow = {s: mdot_species[s] / M_SPECIES[s] for s in mdot_species}      # molecules/s
        ntot = sum(nflow.values()) or 1e-30
        p_s_in = {s: p_in_Pa * nflow[s] / ntot for s in nflow}
        p_s = dict(p_s_in); K_total = {}
        P_gas = 0.0
        # turbomolecular first stage (same shaft speed in rpm; larger radius -> its own tip speed)
        u_t = self.turbo_radius_m * self.rpm * 2 * math.pi / 60.0
        S_t = self.turbo_kS * u_t * self.turbo_area_m2
        for row in range(self.turbo_rows):
            for s in nflow:
                m = M_SPECIES[s]; cb = self._cbar(m)
                K0 = math.exp(self.turbo_kK * u_t / cb)
                Q = nflow[s] * K_B * self.T_gas_K
                K = K0 - (K0 - 1.0) * Q / max(S_t * p_s[s], 1e-30)
                K = max(min(K, K0), 1.0)
                p_mean = 0.5 * p_s[s] * (1 + K)
                P_gas += p_mean * (u_t / cb) * (self.turbo_area_m2 * self.turbo_blade_area_frac * 2) * (2 / math.sqrt(math.pi)) * u_t
                p_s[s] *= K
                K_total[s] = K_total.get(s, 1.0) * K
        for st in range(self.n_stages):
            for s in nflow:
                m = M_SPECIES[s]; cb = self._cbar(m)
                K0 = math.exp(2 * u * L / (cb * h) * self.xi)
                Q = nflow[s] * K_B * self.T_gas_K                                  # Pa m^3/s
                K = K0 - (K0 - 1.0) * Q / max(S0 * p_s[s], 1e-30)
                K = max(min(K, K0), 1.0)
                # free-molecular shear on wetted area at mean channel pressure
                p_mean = 0.5 * p_s[s] * (1 + K)
                A_wet = 2 * L * w
                P_gas += p_mean * (u / cb) * A_wet * (2 / math.sqrt(math.pi)) * u
                p_s[s] *= K
                K_total[s] = K_total.get(s, 1.0) * K
        p_out = sum(p_s.values())
        # leakage back to inlet reduces delivered flow
        leak = {s: self.leak_conductance_m3_s * (p_s[s] - p_s_in[s]) * M_SPECIES[s] / (K_B * self.T_gas_K) for s in nflow}
        delivered = {s: max(mdot_species[s] - leak[s], 0.0) for s in nflow}
        omega = self.rpm * 2 * math.pi / 60.0
        P_bear = self.k_bear_W_per_rads * omega
        P_el = (P_gas + P_bear) / self.eta_motor + self.P_ctrl_W
        torque = (P_gas + P_bear) / omega
        # mass
        rm = DB[self.rotor_material]
        m_rotor = (math.pi * self.rotor_radius_m ** 2 * self.rotor_disc_thickness_m * rm.density * self.n_stages * 0.7
                   + self.turbo_area_m2 * self.turbo_disc_thickness_m * rm.density * self.turbo_rows * self.turbo_blade_area_frac
                   + 0.15 * self.turbo_rows)   # hub/shroud
        m_motor = self.motor_kg_per_Nm * max(torque, 0.01) + 0.25
        mass = m_rotor * (1 + self.stator_mass_factor) + m_motor + self.bearing_kg
        # temperature (lumped)
        T = self.T_sink_K + (P_gas + P_bear * 0.5 + P_el - (P_gas + P_bear) ) / self.conductance_to_sink_W_K
        u_lim = self.u_max()
        return {"u_mps": u, "u_turbo_mps": u_t, "u_max_mps": u_lim, "rotor_ok": max(u, u_t) <= u_lim,
                "S_turbo_m3_s": S_t, "S0_drag_m3_s": S0,
                "p_in_Pa": p_in_Pa, "p_out_Pa": p_out, "CR_active": p_out / p_in_Pa,
                "CR_by_species": K_total, "delivered_kgps": delivered, "leak_kgps": leak,
                "P_gas_W": P_gas, "P_bear_W": P_bear, "P_el_W": P_el, "torque_Nm": torque,
                "mass_kg": mass, "T_comp_K": T,
                "composition_out": {s: p_s[s] / p_out for s in p_s}}

    def rpm_limit(self) -> float:
        r_max = max(self.rotor_radius_m, self.turbo_radius_m)
        return self.u_max() / r_max * 60.0 / (2 * math.pi)

    def size_for(self, p_in_Pa: float, mdot_species: dict, CR_target: float, rpm_max: float = 90000.0,
                 max_turbo_rows: int = 6, max_drag_stages: int = 4) -> dict:
        """Search turbo rows, then drag stages, then rpm (<= rotor stress limit) for the lightest machine
        reaching CR_target. Drag stages are only useful once Q/p is small (p >~ 1 Pa)."""
        rpm_cap = min(rpm_max, self.rpm_limit())
        best = None
        for rows in range(1, max_turbo_rows + 1):
            for nst in range(0, max_drag_stages + 1):
                for rpm in sorted(set(list(range(5000, int(rpm_cap) + 1, 2500)) + [int(rpm_cap)])):
                    self.turbo_rows, self.n_stages, self.rpm = rows, nst, rpm
                    r = self.run(p_in_Pa, mdot_species)
                    if r["CR_active"] >= CR_target:
                        cand = {**r, "turbo_rows": rows, "n_stages": nst, "rpm": rpm, "sized": True}
                        if best is None or cand["mass_kg"] + 0.02 * cand["P_el_W"] < best["mass_kg"] + 0.02 * best["P_el_W"]:
                            best = cand
                        break
        if best:
            self.turbo_rows, self.n_stages, self.rpm = best["turbo_rows"], best["n_stages"], best["rpm"]
            return best
        self.turbo_rows, self.n_stages, self.rpm = max_turbo_rows, 0, int(rpm_cap)
        r = self.run(p_in_Pa, mdot_species)
        return {**r, "turbo_rows": self.turbo_rows, "n_stages": 0, "rpm": self.rpm, "sized": False}
