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
Rotor stress: sigma_hoop ~ rho_rotor u^2. Structural acceptance (owner decision A9.9 S2.3 + MCC-03) is evaluated by
  abep_sim.rotor_strength against a REGISTERED rotor-strength basis (product form, temperature, yield AND ultimate
  allowables, design/test factors, max design speed, proof spin). With no registered basis the rotor is explored as
  PARAMETRIC_SENSITIVITY only: rotor_qualification = NOT_EVALUATED_MATERIAL_BASIS and rotor_ok is False. The tip-speed
  cap then comes from the labelled legacy/conservative sensitivity case u = sqrt(DB yield / (stress_safety rho))
  (uncited DB yield, uncited factor 2.0), which is not a cited requirement.
Mass: rotor (disc + channels), stator, motor (mass ∝ torque), bearings, housing.
Temperature: lumped node, P_loss vs radiative+conductive sink.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional
from .constants import K_B, M_SPECIES
from .materials import DB
from . import rotor_strength as RS


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
    # LEGACY/CONSERVATIVE SENSITIVITY factor only (uncited; A9.9 S2.3). Used solely for the PARAMETRIC_SENSITIVITY
    # tip-speed cap when no rotor-strength basis is registered; never a qualification criterion.
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

    # A9.9 S2.3: id of a REGISTERED basis in abep_sim.rotor_strength.REGISTRY (None = none registered) and the actual
    # rotor stock thickness/section the basis must cover. Deliberately NOT dataclass fields (unannotated class defaults):
    # they are qualification evidence, not design/sizing coefficients, so the existing field-enumerating design-input
    # contracts are not changed by this model change. Set per instance with set_rotor_strength_basis().
    rotor_strength_basis_id = None
    rotor_stock_thickness_m = None

    def set_rotor_strength_basis(self, basis_id: Optional[str], stock_thickness_m: Optional[float]) -> "DragCompressor":
        self.rotor_strength_basis_id = basis_id
        self.rotor_stock_thickness_m = stock_thickness_m
        return self

    @property
    def u(self) -> float:
        return self.rotor_radius_m * self.rpm * 2 * math.pi / 60.0

    def u_max_legacy_sensitivity(self) -> float:
        """LEGACY/CONSERVATIVE SENSITIVITY tip-speed cap: uncited materials.DB yield / (uncited stress_safety * rho).
        Not a cited allowable and not a qualification basis (A9.9 S2.3 / MCC-03)."""
        m = DB[self.rotor_material]
        return math.sqrt(m.yield_MPa * 1e6 / (self.stress_safety * m.density))

    def registered_basis(self):
        return RS.get_registered(self.rotor_strength_basis_id)

    def sizing_mode(self) -> str:
        b = self.registered_basis()
        ok = b is not None and not RS.basis_problems(b) and b.materials_db_key == self.rotor_material
        return RS.SIZING_REGISTERED_BASIS if ok else RS.SIZING_PARAMETRIC_SENSITIVITY

    def u_max(self) -> float:
        """Tip-speed cap used for sizing: from the registered basis (both yield and ultimate at the design temperature)
        when one applies to this rotor material, otherwise the labelled legacy sensitivity cap (see ``u_max_basis``)."""
        if self.sizing_mode() == RS.SIZING_REGISTERED_BASIS:
            return RS.tip_speed_allowable(self.registered_basis())
        return self.u_max_legacy_sensitivity()

    def u_max_basis(self) -> str:
        if self.sizing_mode() == RS.SIZING_REGISTERED_BASIS:
            return f"REGISTERED_BASIS:{self.rotor_strength_basis_id}"
        return RS.LEGACY_SENSITIVITY_LABEL

    def _cbar(self, m):
        return math.sqrt(8 * K_B * self.T_gas_K / (math.pi * m))

    # G-03 (owner decision A9.9 S2.4): the recirculation fixed point is reported explicitly. Reaching the
    # iteration limit is NOT convergence.
    RECIRC_MAX_ITER = 40
    RECIRC_RTOL = 1e-4

    def run(self, p_in_Pa: float, mdot_species: dict, self_consistent: bool = True) -> dict:
        """Operating point with leakage solved self-consistently (document 16, item 13): the leak path returns gas
        from the outlet to the inlet, so the machine's throughput is (captured + recirculated). Iterate
        Q_through = Q_captured + Q_leak(p_out(Q_through)) to a fixed point; delivered = captured (steady state:
        everything captured eventually leaves through the outlet), but p_out and CR are those at the higher throughput.

        Convergence (G-03): the result carries ``converged`` (bool), ``iterations`` (number of machine
        evaluations), ``residual`` (final max_s |Q_leak,s - Q_recirc,s| / max(mdot_s, 1e-15), compared with
        RECIRC_RTOL) and ``solver_status`` ('CONVERGED', 'MODEL_NOT_CONVERGED' or 'DIRECT_EVALUATION' when
        self_consistent=False). A non-converged result keeps its raw last-iterate state for diagnostics but must
        not be admitted as a valid operating point.

        Gaede domain (MCC-02, owner decision A9.9 S2.5): every record also carries the UNCLIPPED Gaede characteristic
        per stage and species (``gaede_K_unclipped`` {stage: {species: K}}, ``gaede_stages`` with K0, throughput,
        capacity and load ratio), ``gaede_domain_ok`` and ``gaede_status`` ('IN_DOMAIN' or
        'OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY'). Out of domain (some unclipped K < 1: throughput above stage capacity),
        the cascade is continued with the clipped K = 1 only as a labelled diagnostic (``K_clipped_diagnostic``,
        ``gaede_clipped_values_are_diagnostic``); such a record is not valid design evidence."""
        if not self_consistent:
            r = self._run_once(p_in_Pa, mdot_species)
            r.update({"converged": True, "iterations": 1, "residual": 0.0, "solver_status": "DIRECT_EVALUATION"})
            return r
        recirc = {s: 0.0 for s in mdot_species}
        r = None; converged = False; it = 0; resid = float("nan")
        for _ in range(self.RECIRC_MAX_ITER):
            through = {s: mdot_species[s] + recirc[s] for s in mdot_species}
            r = self._run_once(p_in_Pa, through); it += 1
            new = {s: max(r["leak_kgps"][s], 0.0) for s in mdot_species}
            resid = max((abs(new[s] - recirc[s]) / max(mdot_species[s], 1e-15) for s in mdot_species), default=0.0)
            if all(abs(new[s] - recirc[s]) <= self.RECIRC_RTOL * max(mdot_species[s], 1e-15) for s in mdot_species):
                recirc = new; converged = True; break
            recirc = {s: 0.5 * (recirc[s] + new[s]) for s in mdot_species}
        r["recirculated_kgps"] = recirc
        r["recirculation_frac"] = sum(recirc.values()) / max(sum(mdot_species.values()), 1e-30)
        r["delivered_kgps"] = dict(mdot_species)          # steady state: outflow = captured inflow
        r["leak_kgps"] = recirc
        r.update({"converged": converged, "iterations": it, "residual": resid,
                  "solver_status": "CONVERGED" if converged else "MODEL_NOT_CONVERGED"})
        return r

    # MCC-02 (owner decision A9.9 S2.5, finding F3-01): Gaede stage-capacity domain. The linear characteristic
    # K = K0 - (K0 - 1) Q / (S p) gives K < 1 when the stage throughput Q exceeds its capacity S p: the stage cannot
    # pass that flow and the model has no admitted steady state there. That state is NOT converted into a valid K = 1
    # result: the unclipped K is preserved and reported, and the record is flagged out of the admitted model domain.
    GAEDE_IN_DOMAIN = "IN_DOMAIN"
    GAEDE_OUT_OF_DOMAIN = "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY"

    @staticmethod
    def _gaede_record(gaede: list, stage: str, species: str, K_raw: float, K0: float, Q: float, capacity: float) -> float:
        """Record the unclipped Gaede characteristic of one stage/species and return the value propagated through
        the cascade. In the admitted domain (1 <= K_raw <= K0) that is K_raw itself (bit-identical to before). Out
        of domain (K_raw < 1) the propagated value is the clipped K = 1, which is a LABELLED DIAGNOSTIC only: every
        quantity computed downstream of it is diagnostic and the record is flagged OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY.
        (K_raw > K0 would need Q < 0 and cannot occur for non-negative flows.)"""
        in_domain = 1.0 <= K_raw <= K0
        K_diag = max(min(K_raw, K0), 1.0)
        gaede.append({"stage": stage, "species": species, "K_unclipped": K_raw, "K0": K0,
                      "throughput_Pa_m3_s": Q, "capacity_Pa_m3_s": capacity,
                      "load_ratio": Q / max(capacity, 1e-30), "in_domain": in_domain,
                      "K_clipped_diagnostic": None if in_domain else K_diag})
        return K_raw if in_domain else K_diag

    @classmethod
    def _gaede_summary(cls, gaede: list) -> dict:
        out = [g for g in gaede if not g["in_domain"]]
        by_stage = {}
        for g in gaede:
            by_stage.setdefault(g["stage"], {})[g["species"]] = g["K_unclipped"]
        ok = not out
        return {"gaede_domain_ok": ok,
                "gaede_status": cls.GAEDE_IN_DOMAIN if ok else cls.GAEDE_OUT_OF_DOMAIN,
                "gaede_K_unclipped": by_stage,
                "gaede_K_unclipped_min": min((g["K_unclipped"] for g in gaede), default=float("nan")),
                "gaede_out_of_domain": [f"{g['stage']}:{g['species']}" for g in out],
                "gaede_stages": gaede,
                # labelled diagnostic: p_out / CR / power / leak downstream of an overloaded stage use the clipped K
                "gaede_clipped_values_are_diagnostic": not ok}

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
        gaede = []        # MCC-02: one record per stage x species, with the UNCLIPPED Gaede characteristic
        # turbomolecular first stage (same shaft speed in rpm; larger radius -> its own tip speed)
        u_t = self.turbo_radius_m * self.rpm * 2 * math.pi / 60.0
        S_t = self.turbo_kS * u_t * self.turbo_area_m2
        for row in range(self.turbo_rows):
            for s in nflow:
                m = M_SPECIES[s]; cb = self._cbar(m)
                K0 = math.exp(self.turbo_kK * u_t / cb)
                Q = nflow[s] * K_B * self.T_gas_K
                K_raw = K0 - (K0 - 1.0) * Q / max(S_t * p_s[s], 1e-30)
                K = self._gaede_record(gaede, f"turbo_row_{row + 1}", s, K_raw, K0, Q, S_t * p_s[s])
                p_mean = 0.5 * p_s[s] * (1 + K)
                P_gas += p_mean * (u_t / cb) * (self.turbo_area_m2 * self.turbo_blade_area_frac * 2) * (2 / math.sqrt(math.pi)) * u_t
                p_s[s] *= K
                K_total[s] = K_total.get(s, 1.0) * K
        for st in range(self.n_stages):
            for s in nflow:
                m = M_SPECIES[s]; cb = self._cbar(m)
                K0 = math.exp(2 * u * L / (cb * h) * self.xi)
                Q = nflow[s] * K_B * self.T_gas_K                                  # Pa m^3/s
                K_raw = K0 - (K0 - 1.0) * Q / max(S0 * p_s[s], 1e-30)
                K = self._gaede_record(gaede, f"drag_stage_{st + 1}", s, K_raw, K0, Q, S0 * p_s[s])
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
        u_leg = self.u_max_legacy_sensitivity()
        # A9.9 S2.3 / MCC-03: structural acceptance only against a registered basis (fail closed otherwise)
        q = RS.qualify_rotor(self.rotor_strength_basis_id, self.rotor_material, max(u, u_t), self.rpm, T,
                             self.rotor_stock_thickness_m)
        return {"u_mps": u, "u_turbo_mps": u_t, "u_max_mps": u_lim, "u_max_basis": self.u_max_basis(),
                "sizing_mode": self.sizing_mode(), **q, "rotor_ok": q["rotor_ok"],
                "u_max_legacy_sensitivity_mps": u_leg,
                "rotor_within_legacy_sensitivity_cap": max(u, u_t) <= u_leg,
                "S_turbo_m3_s": S_t, "S0_drag_m3_s": S0,
                "p_in_Pa": p_in_Pa, "p_out_Pa": p_out, "CR_active": p_out / p_in_Pa,
                "CR_by_species": K_total, "delivered_kgps": delivered, "leak_kgps": leak,
                "P_gas_W": P_gas, "P_bear_W": P_bear, "P_el_W": P_el, "torque_Nm": torque,
                "mass_kg": mass, "T_comp_K": T,
                "composition_out": {s: p_s[s] / p_out for s in p_s},
                **self._gaede_summary(gaede)}

    def rpm_limit(self) -> float:
        r_max = max(self.rotor_radius_m, self.turbo_radius_m)
        return self.u_max() / r_max * 60.0 / (2 * math.pi)

    def size_for(self, p_in_Pa: float, mdot_species: dict, CR_target: float, rpm_max: float = 90000.0,
                 max_turbo_rows: int = 6, max_drag_stages: int = 4) -> dict:
        """Search turbo rows, then drag stages, then rpm (<= rotor tip-speed cap) for the lightest machine
        reaching CR_target. Drag stages are only useful once Q/p is small (p >~ 1 Pa).

        A9.9 S2.3 / MCC-03: the rpm cap comes from ``u_max()``; with no registered rotor-strength basis this is the
        labelled legacy sensitivity cap and the record says ``sizing_mode='PARAMETRIC_SENSITIVITY'``,
        ``rotor_qualification='NOT_EVALUATED_MATERIAL_BASIS'``, ``rotor_ok=False``: such a result is exploration,
        never a qualified rotor.

        MCC-02 (A9.9 S2.5): only layouts whose every stage/species is inside the Gaede stage-capacity domain
        (unclipped 1 <= K <= K0, ``gaede_domain_ok``) are admitted as sized designs; an out-of-domain state that meets
        CR_target through clipped stages is counted (``n_rejected_out_of_gaede_domain``) and never selected. The
        unsized fallback carries its own ``gaede_status`` (its values are clipped diagnostics when out of domain).

        G-03: the search itself is otherwise unchanged; the returned record carries the convergence fields of the selected
        run() (``converged``, ``iterations``, ``residual``, ``solver_status``). Callers must treat
        ``converged=False`` (``solver_status='MODEL_NOT_CONVERGED'``) as not admissible."""
        rpm_cap = min(rpm_max, self.rpm_limit())
        best = None; n_ood = 0
        for rows in range(1, max_turbo_rows + 1):
            for nst in range(0, max_drag_stages + 1):
                for rpm in sorted(set(list(range(5000, int(rpm_cap) + 1, 2500)) + [int(rpm_cap)])):
                    self.turbo_rows, self.n_stages, self.rpm = rows, nst, rpm
                    r = self.run(p_in_Pa, mdot_species)
                    if r["CR_active"] >= CR_target:
                        if not r["gaede_domain_ok"]:
                            # MCC-02: a CR reached through an overloaded (clipped) stage is diagnostic, not a design;
                            # keep searching this layout at higher rpm (capacity grows with tip speed)
                            n_ood += 1
                            continue
                        cand = {**r, "turbo_rows": rows, "n_stages": nst, "rpm": rpm, "sized": True}
                        if best is None or cand["mass_kg"] + 0.02 * cand["P_el_W"] < best["mass_kg"] + 0.02 * best["P_el_W"]:
                            best = cand
                        break
        if best:
            self.turbo_rows, self.n_stages, self.rpm = best["turbo_rows"], best["n_stages"], best["rpm"]
            return {**best, "n_rejected_out_of_gaede_domain": n_ood}
        self.turbo_rows, self.n_stages, self.rpm = max_turbo_rows, 0, int(rpm_cap)
        r = self.run(p_in_Pa, mdot_species)
        # Unsized fallback (CR target not reached by any in-domain layout). If it is itself outside the Gaede domain,
        # its p_out / CR / power / mass are clipped-K diagnostics only (gaede_status says so).
        return {**r, "turbo_rows": self.turbo_rows, "n_stages": 0, "rpm": self.rpm, "sized": False,
                "n_rejected_out_of_gaede_domain": n_ood}
