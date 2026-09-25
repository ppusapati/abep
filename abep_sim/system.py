"""Close one ABEP configuration against every RFP constraint."""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from typing import Optional
from .constants import RFP, G0
from .atmosphere import atmosphere
from .intake import IntakeParams, CompressorParams, collection, compress
from .thruster import CARDS, performance, xe_for_thrust
from .aochem import AOParams, inlet_composition, ao_flux, fluence, erosion_depth_um


@dataclass
class Budgets:
    ppu_eff: float = 0.90
    p_ctrl_valves_sensors_W: float = 30.0
    p_margin_frac: float = 0.10          # held against 1.5 kW
    m_ppu_base_kg: float = 3.5
    m_ppu_per_kW_kg: float = 2.0
    m_structure_frac: float = 0.10       # of dry propulsion mass
    m_xe_tank_frac: float = 0.25         # tank mass per kg Xe
    m_xe_tank_base_kg: float = 0.8
    m_margin_frac: float = 0.10          # kept for back-compat; reported explicitly as contingency below
    mga_new_design: float = 0.30         # mass growth allowance, new/low-TRL items (intake, compressor, stage1)
    mga_modified: float = 0.15           # modified heritage (thruster, PPU)
    mga_existing: float = 0.05           # existing (tanks, structure)
    m_cbe_target_kg: float = 32.0        # internal target for current best estimate
    ic_intake: float = 0.90
    ic_compressor: float = 0.65
    ic_pse: float = 0.80
    ic_structure: float = 0.95
    duty_cycle: float = RFP.ignition_hours / RFP.mission_hours   # ~0.58
    xe_aug_hours: float = 1500.0         # hours of Xe-augmented (peak) operation budgeted


@dataclass
class Config:
    architecture: str
    alt_km: float = 200.0
    solar: str = "mean"
    intake: IntakeParams = None
    compressor: CompressorParams = None
    vd_V: Optional[float] = None
    accommodation: Optional[float] = None
    T_required_mN: Optional[float] = None   # if None, use RFP 12 mN floor
    body_area_m2: float = 0.0               # spacecraft frontal area beyond the intake (DRDO input, unknown)
    gaspath_physics: bool = False           # Phase 2: drag-compressor + reservoir network instead of parametric
    plasma_physics: bool = False            # Phase 3: global chemistry + source coupling + interstage + Hall channel + cathode
    s1_power_dc_W: Optional[float] = None   # override pre-ioniser DC power (physics path); None -> card prior
    hall_L_m: float = 0.10                  # Hall channel length (physics path)
    hall_wall: str = "BN"
    engineering_physics: bool = False       # Phase 4: PPU maps + loads, thermal network + radiator, life, BOM
    hall_r_in_m: float = 0.020
    hall_r_out_m: float = 0.035
    hall_B_T: float = 0.020
    hall_wall_mm: float = 4.0
    hall_shielding: float = 0.08            # wall ion-flux fraction (magnetic shielding quality)
    blade_coating_um: float = 20.0
    xe_aug_hours: Optional[float] = None    # override Budgets.xe_aug_hours (augmentation reserve)
    rotor_material: str = "CFRP"
    reservoir_material: str = "Al2O3_anodised"
    p_margin_over_pmin: float = 3.0
    p_target_Pa: Optional[float] = None     # absolute reservoir pressure target (overrides margin x p_min) — architecture-neutral
    budgets: Budgets = None
    ao: AOParams = None

    def __post_init__(self):
        self.ao = self.ao or AOParams()
        self.intake = self.intake or IntakeParams()
        self.compressor = self.compressor or CompressorParams()
        self.budgets = self.budgets or Budgets()
        if self.accommodation is not None:
            self.intake.accommodation = self.accommodation
        self.intake.body_area_m2 = self.body_area_m2
        if self.xe_aug_hours is not None:
            self.budgets.xe_aug_hours = self.xe_aug_hours


def evaluate(cfg: Config) -> dict:
    card = CARDS[cfg.architecture]
    b = cfg.budgets
    atm = atmosphere(cfg.alt_km, cfg.solar)
    col = collection(cfg.intake, atm)
    cmp_ = compress(cfg.compressor, atm, col["mdot_collected"], col["eta_c"], col["passive_override"])
    mdot_air = cmp_["mdot_net"]
    p_in = cmp_["p_out_Pa"]

    # AO chemistry: what the thruster actually receives after wall recombination
    inlet = inlet_composition(atm, cfg.ao)
    gas = {}
    if cfg.gaspath_physics:
        from .compressor import DragCompressor
        from .reservoir import Reservoir, size_orifice_for_pressure
        p_min = card.p_min_Pa if card.stage1 is None else max(card.p_min_Pa, card.stage1.p_min_Pa)
        p_target = cfg.p_target_Pa if cfg.p_target_Pa is not None else cfg.p_margin_over_pmin * p_min
        md_in = {"O": mdot_air * atm["fO"], "N2": mdot_air * atm["fN2"], "O2": mdot_air * atm["fO2"]}
        comp = DragCompressor(turbo_area_m2=min(0.45, 0.9 * cfg.intake.area_m2 * cfg.intake.phi),
                              turbo_radius_m=min(0.45, math.sqrt(cfg.intake.area_m2 / math.pi)),
                              rotor_material=cfg.rotor_material)
        cr_needed = max(p_target / max(cmp_["p_passive_Pa"], 1e-9), 1.0)
        cres = comp.size_for(cmp_["p_passive_Pa"], md_in, CR_target=cr_needed)
        res = Reservoir(wall_material=cfg.reservoir_material, upstream_material=cfg.rotor_material if cfg.rotor_material in ("Ti6Al4V", "Al6061") else "Al2O3_anodised",
                        upstream_collisions=10.0 * cres["turbo_rows"] + 50.0 * cres["n_stages"], T_K=min(max(cres["T_comp_K"], 300.0), 500.0))
        size_orifice_for_pressure(res, cres["delivered_kgps"], min(p_target, cres["p_out_Pa"]))
        rs = res.steady_state(cres["delivered_kgps"])
        mdot_air = sum(rs["mdot_anode"].values())
        p_in = rs["p_total_Pa"]
        comp_mass = cres["mass_kg"]; comp_power = cres["P_el_W"]
        fr = rs["composition_anode_mass"]
        inlet = {"fO": fr.get("O", 0.0), "fN2": fr.get("N2", 0.0), "fO2": fr.get("O2", 0.0), "O_survival": rs["O_survival"],
                 "diss_sink_J_per_kg": fr.get("O2", 0.0) * (5.12 * 1.602176634e-19) / (32.0 * 1.66053906660e-27)}
        gas = {"comp_sized": cres["sized"], "comp_turbo_rows": cres["turbo_rows"], "comp_drag_stages": cres["n_stages"],
               "comp_rpm": cres["rpm"], "comp_tip_mps": cres["u_turbo_mps"], "comp_CR_active": cres["CR_active"],
               "comp_CR_O": cres["CR_by_species"].get("O", 1.0), "comp_CR_N2": cres["CR_by_species"].get("N2", 1.0),
               "comp_T_K": cres["T_comp_K"], "res_p_Pa": rs["p_total_Pa"], "res_tau_ms": rs["residence_time_s"] * 1e3,
               "res_wall_collisions": rs["wall_collisions_reservoir"], "gamma_wall": rs["gamma_wall"],
               "p_target_Pa": p_target, "cr_needed": cr_needed}
        cmp_ = {**cmp_, "p_out_Pa": p_in, "comp_power_W": comp_power, "comp_mass_kg": comp_mass,
                "active_ratio": cres["CR_active"], "comp_feasible": cres["sized"] and cres["rotor_ok"], "mdot_net": mdot_air}
    atm_in = {**atm, "fO": inlet["fO"], "fN2": inlet["fN2"], "fO2": inlet["fO2"],
              "diss_sink_J_per_kg": inlet["diss_sink_J_per_kg"]}
    ao = ao_flux(atm)
    fl = fluence(atm, RFP.mission_hours)

    air = performance(card, atm_in, mdot_air, p_in, cfg.vd_V)
    plasma = {}
    if cfg.plasma_physics and card.family == "hall":
        from .plasma_chem import Chamber, solve_global
        from .plasma_devices import ECRSource, RFSource, Interstage, HallChannel, LaB6Cathode
        vd = card.vd_default_V if cfg.vd_V is None else cfg.vd_V
        flows = {"O": mdot_air * atm_in["fO"], "N2": mdot_air * atm_in["fN2"], "O2": mdot_air * atm_in["fO2"]}
        preion = {}; eta_t = 0.0; P_s1_dc = 0.0; st = None
        if card.stage1 is not None:
            P_s1_dc = (card.stage1.power_fixed_W + card.stage1.power_per_mgps_W * mdot_air * 1e6) / card.stage1.source_eff
            if cfg.s1_power_dc_W is not None:
                P_s1_dc = cfg.s1_power_dc_W
            src = ECRSource(P_dc_W=P_s1_dc) if card.stage1.kind == "ecr" else RFSource(P_dc_W=P_s1_dc)
            ch = Chamber(magnetised_wall_factor=0.3 if card.stage1.kind == "ecr" else 0.5)
            P_abs, eta_c1 = src.absorbed(p_in)
            st = solve_global(ch, flows, P_abs, f_cutoff_Hz=2.45e9 if card.stage1.kind == "ecr" else None)
            P_abs, eta_c1 = src.absorbed(p_in, st.n_e)          # overdense / loading correction, one pass
            st = solve_global(ch, flows, P_abs, f_cutoff_Hz=2.45e9 if card.stage1.kind == "ecr" else None)
            tot_i = sum(st.ion_exit_A.values()) or 1.0
            tr = Interstage().transport(st.Te_eV, {i: st.ion_exit_A[i] / tot_i for i in st.ion_exit_A}, p_in)
            eta_t = tr["eta_transport"]
            preion = {i: st.ion_exit_A[i] * tr["eta_by_ion"][i] for i in st.ion_exit_A}
            # neutrals that leave the ioniser un-ionised continue into the Hall channel
            from .plasma_chem import M_NEUT
            import math as _m
            cbar = {sname: _m.sqrt(8 * 1.380649e-23 * ch.T_gas_K / (_m.pi * M_NEUT[sname])) for sname in ("O", "O2", "N2", "N")}
            flows = {sname: st.n_neut[sname] * ch.exit_neutral_K * ch.exit_area_m2 * cbar[sname] / 4.0 * M_NEUT[sname] for sname in ("O", "O2", "N2", "N")}
        hc = HallChannel(wall_material=cfg.hall_wall, L_m=cfg.hall_L_m, magnetic_shielding=cfg.hall_shielding,
                         r_in_m=cfg.hall_r_in_m, r_out_m=cfg.hall_r_out_m, B_max_T=cfg.hall_B_T)
        hr = hc.run(vd, flows, preion)
        cath = LaB6Cathode().operate(max(hr["I_d_A"], 0.5), p_in * atm_in["fO"] * 0.1)
        T_N = hr["T_N"]
        P_thr = hr["P_d_W"] + P_s1_dc + card.p_magnet_W + cath["P_W"]
        mdot_tot = mdot_air + card.cathode.xe_flow_mgps * 1e-6
        from .plasma_chem import M_ION as _MI
        beam_mass = sum(hr["I_beam_by_ion"][i] / 1.602176634e-19 * _MI[i] for i in hr["I_beam_by_ion"])
        util_total = beam_mass / max(mdot_air, 1e-30)          # beam mass utilisation (thrust-producing)
        util_consumed = 1.0 - sum(hr["neutral_out_kgps"].values()) / max(mdot_air, 1e-30)
        air = {**air, "T_N": T_N, "P_thruster_W": P_thr, "P_discharge_W": hr["P_d_W"], "P_stage1_W": P_s1_dc,
               "eta_u_air": util_total, "Isp_s": T_N / (G0 * mdot_tot) if mdot_tot > 0 else 0.0,
               "I_beam_A": hr["I_beam_A"], "eta_b": hr["eta_b"], "vd_V": vd,
               "eta_thruster": (T_N ** 2 / (2 * mdot_tot * P_thr)) if P_thr > 0 else 0.0}
        plasma = {"pl_Te_hall_eV": hr["Te_eV"], "pl_Te_see_limit_eV": hr["Te_see_limit_eV"], "pl_ne_hall": hr["n_e"],
                  "pl_I_d_A": hr["I_d_A"], "pl_eta_b": hr["eta_b"], "pl_util_hall_only": hr["util_hall"], "pl_f_cx": hr["f_cx"],
                  "pl_m_ion_amu": hr["m_ion_mean_amu"], "pl_wall_erosion_um_per_kh": hr["wall_erosion_um_per_kh"],
                  "pl_util_beam": util_total, "pl_util_consumed": util_consumed, "pl_eta_transport": eta_t,
                  "pl_preion_A": sum(preion.values()),
                  "pl_s1_Te_eV": st.Te_eV if st else 0.0, "pl_s1_ne": st.n_e if st else 0.0,
                  "pl_s1_util": st.util_total if st else 0.0, "pl_s1_eV_per_ion": st.eV_per_usable_ion if st else 0.0,
                  "pl_s1_P_abs_W": st.P_abs_W if st else 0.0, "pl_s1_overdense": st.overdense_ratio if st else 0.0,
                  "pl_s1_dissO2": st.diss_frac["O2"] if st else 0.0, "pl_s1_dissN2": st.diss_frac["N2"] if st else 0.0,
                  "pl_cath_T_K": cath["T_emitter_K"], "pl_cath_coverage": cath["coverage"], "pl_cath_P_W": cath["P_W"],
                  "pl_cath_life_h": cath["life_h_evaporation"], "pl_sustained": hr["I_beam_A"] > 0.05}
    T_air = air["T_N"]

    # Sustained thrust requirement: RFP floor (12 mN) unless overridden. Drag of the
    # ram face is reported separately as T/D so closure is visible, not hidden in Xe.
    drag = col["drag_N"]
    T_req = (cfg.T_required_mN * 1e-3) if cfg.T_required_mN else RFP.thrust_min_mN * 1e-3
    T_req = min(T_req, RFP.thrust_max_mN * 1e-3)

    # Xe augmentation to reach the 25 mN peak point (and to reach T_req if air is short)
    xe_peak = xe_for_thrust(card, atm_in, mdot_air, p_in, RFP.thrust_max_mN * 1e-3, cfg.vd_V)
    peak = performance(card, atm_in, mdot_air, p_in, cfg.vd_V, mdot_xe_anode=xe_peak)
    xe_req = xe_for_thrust(card, atm_in, mdot_air, p_in, T_req, cfg.vd_V)

    # Power (air mode and peak mode)
    def total_power(perf):
        bus = (perf["P_thruster_W"] + cmp_["comp_power_W"] + b.p_ctrl_valves_sensors_W) / b.ppu_eff
        return bus
    P_air = total_power(air)
    P_peak = total_power(peak)
    P_cap = RFP.power_max_W * (1 - b.p_margin_frac)

    # Xe mass over mission
    xe_cath_kg = card.cathode.xe_flow_mgps * 1e-6 * RFP.ignition_hours * 3600
    xe_aug_kg = xe_peak * b.xe_aug_hours * 3600
    xe_req_kg = xe_req * RFP.ignition_hours * 3600       # if air alone can't meet T_req all the time
    xe_total_kg = xe_cath_kg + xe_aug_kg + xe_req_kg

    # Mass
    m_thr = card.mass_kg + (card.stage1.mass_kg if card.stage1 else 0.0)
    m_ppu = b.m_ppu_base_kg + b.m_ppu_per_kW_kg * (P_peak / 1000.0)
    m_intake = col["intake_mass_kg"]
    m_comp = cmp_["comp_mass_kg"]
    m_xe_sys = xe_total_kg + b.m_xe_tank_base_kg + b.m_xe_tank_frac * xe_total_kg
    m_dry = m_thr + m_ppu + m_intake + m_comp + b.m_xe_tank_base_kg + b.m_xe_tank_frac * xe_total_kg
    m_struct = b.m_structure_frac * m_dry
    m_total = (m_dry + m_struct + xe_total_kg) * (1 + b.m_margin_frac)
    # CBE / MGA / MEV (item-class growth allowances instead of a flat hidden margin)
    m_tank = b.m_xe_tank_base_kg + b.m_xe_tank_frac * xe_total_kg
    m_cbe = m_thr + m_ppu + m_intake + m_comp + m_tank + m_struct + xe_total_kg
    m_mga = (b.mga_new_design * (m_intake + m_comp + (card.stage1.mass_kg if card.stage1 else 0.0))
             + b.mga_modified * (card.mass_kg + m_ppu) + b.mga_existing * (m_tank + m_struct))
    m_mev = m_cbe + m_mga

    # Indigenous content (mass-weighted, dry)
    ic_thr = card.ic_thruster
    if card.stage1:
        ic_thr = (card.mass_kg * card.ic_thruster + card.stage1.mass_kg * card.stage1.ic) / m_thr
    ic_num = (m_thr * ic_thr + m_intake * b.ic_intake + m_comp * b.ic_compressor
              + m_ppu * b.ic_pse + m_struct * b.ic_structure)
    ic_total = ic_num / (m_thr + m_intake + m_comp + m_ppu + m_struct)

    # Life: O-exposed component lives scaled by air-operation hours; cathode as separate item
    air_hours = RFP.ignition_hours
    life_items = dict(card.o_life_h)
    if card.cathode.kind == "mw_air":
        life_items["cathode"] = card.cathode.o_life_h
    life_h = min(life_items.values()) if life_items else 1e9
    life_margin = life_h / air_hours

    T_over_D = T_air / drag if drag > 0 else float("inf")


    checks = {
        "thrust_air_ge_req": T_air >= T_req,
        "thrust_peak_25mN": peak["T_N"] >= RFP.thrust_max_mN * 1e-3 * 0.999,
        "power_air": P_air <= P_cap,
        "power_peak": P_peak <= P_cap,
        "mass": m_total <= RFP.mass_max_kg,
        "life": life_margin >= 1.0,
        "ic_total": ic_total >= RFP.ic_total_min,
        "ic_thruster": ic_thr >= RFP.ic_subsystem_min["thruster"],
        "compressor_feasible": cmp_["comp_feasible"],
        "hall_preferred": card.hall,
        "net_drag_comp_air": T_over_D >= 1.0,
    }
    hard = ["thrust_air_ge_req", "thrust_peak_25mN", "power_air", "power_peak", "mass", "life",
            "ic_total", "ic_thruster", "compressor_feasible"]
    rfp_compliant = all(checks[k] for k in hard)          # meets every stated RFP limit
    abep_closed = rfp_compliant and checks["net_drag_comp_air"]   # AND physically does the job: T > D on air
    technical = [k for k in hard if k not in ("ic_total", "ic_thruster")]
    technical_compliant = all(checks[k] for k in technical)        # physics/engineering only, no IC
    technical_closed = technical_compliant and checks["net_drag_comp_air"]
    feasible = rfp_compliant

    eng = {}
    if cfg.engineering_physics:
        from .ppu import default_ppu, load_modes
        from .thermal import default_nodes, size_radiator, ThermalParams
        from .life import (LifeInputs, hall_channel_life, intake_life, blade_life, magnet_life, cathode_life,
                           compressor_life, reliability)
        from .mass_bom import xe_tank, reservoir_vessel, hall_magnetic_circuit, hall_channel_mass, structure_mass, build_bom
        vd = air["vd_V"]
        I_d = plasma.get("pl_I_d_A", air["I_beam_A"] / max(air["eta_b"], 0.3))
        I_beam = air["I_beam_A"]
        P_s1 = air["P_stage1_W"]
        eta_s1 = 0.65 if (card.stage1 and card.stage1.kind == "ecr") else 0.8
        P_comp = cmp_["comp_power_W"]
        P_cath = plasma.get("pl_cath_P_W", card.cathode.power_W)
        # --- PPU and loads
        ppu = default_ppu(vd, max(I_d, 1.0), card.stage1 is not None, card.stage1.kind if card.stage1 else "", P_s1, max(P_comp, 20.0))
        modes = load_modes(ppu, I_d, card.p_magnet_W / 12.0, 1.5, P_s1, P_comp)
        # thermal iteration: PPU temperature -> efficiency derate (one pass)
        nodes = default_nodes(air["P_discharge_W"], I_beam, vd, P_s1, eta_s1, P_comp, P_cath, modes["steady"]["P_loss_W"],
                              cfg.intake.area_m2)
        rad = size_radiator(nodes, ThermalParams(), atm["rho"], atm.get("V_rel", atm["V"]))
        T_ppu = rad["hot"]["T"]["ppu"]
        modes = load_modes(ppu, I_d, card.p_magnet_W / 12.0, 1.5, P_s1, P_comp, T_K=T_ppu)
        P_bus_steady = modes["steady"]["P_bus_W"] + b.p_ctrl_valves_sensors_W * 0.0
        P_bus_start = modes["startup"]["P_bus_W"]
        # peak: Xe-augmented point uses the same converters with higher anode current
        I_d_peak = peak["I_beam_A"] / max(peak["eta_b"], 0.3) if peak["I_beam_A"] > 0 else I_d
        P_bus_peak = load_modes(ppu, max(I_d_peak, I_d), card.p_magnet_W / 12.0, 1.5, P_s1, P_comp, T_K=T_ppu)["steady"]["P_bus_W"]
        # --- life
        li = LifeInputs(hall_wall_material=cfg.hall_wall, hall_wall_thickness_mm=cfg.hall_wall_mm,
                        hall_sputter_um_per_kh=plasma.get("pl_wall_erosion_um_per_kh", 150.0),
                        intake_alpha0=cfg.intake.accommodation, ao_flux_ram_m2_s=ao["ao_flux"],
                        blade_tip_mps=gas.get("comp_tip_mps", 350.0), V_rel_mps=atm.get("V_rel", atm["V"]),
                        blade_coating_um=cfg.blade_coating_um,
                        magnet_T_K=rad["hot"]["T"]["magnets"], cathode_T_K=plasma.get("pl_cath_T_K", 1750.0),
                        cathode_starts=int(RFP.mission_hours / 24 * 0.5))
        L_hall = hall_channel_life(li); L_int = intake_life(li); L_bl = blade_life(li); L_mag = magnet_life(li)
        L_cat = cathode_life(li); L_cmp = compressor_life(li)
        rel = reliability(li, {"hall_channel": L_hall["life_h"], "cathode": L_cat["life_evaporation_h"],
                               "blade_coating": L_bl["coating_life_h"], "bearings": L_cmp["bearing_life_h"]})
        # --- BOM
        m_mag = hall_magnetic_circuit(cfg.hall_B_T, cfg.hall_r_in_m, cfg.hall_r_out_m, cfg.hall_L_m)
        m_ch = hall_channel_mass(cfg.hall_r_in_m, cfg.hall_r_out_m, cfg.hall_L_m, cfg.hall_wall_mm, cfg.hall_wall)
        xe_kg = xe_cath_kg + xe_aug_kg          # mission Xe: cathode over 15,000 h + augmentation reserve
        tank = xe_tank(max(xe_kg, 0.5))
        resv = reservoir_vessel(2.0e-3)
        pm = ppu.mass(max(P_bus_peak, P_bus_start))
        parts = {"intake": col["intake_mass_kg"], "filter": 0.8 * cfg.intake.area_m2 if cfg.intake.filter else 0.0,
                 "compressor": cmp_["comp_mass_kg"], "reservoir": resv["mass_kg"], "feed_valves_lines": 0.6,
                 "hall_channel": m_ch, "hall_magnetics": m_mag["mass_kg"],
                 "stage1_hardware": card.stage1.mass_kg if card.stage1 else 0.0,
                 "cathode_assy": 1.1, "xe_propellant": xe_kg, "xe_tank": tank["mass_kg"],
                 "ppu_converters": pm["m_converters_kg"], "ppu_control_sensors": pm["m_controller_kg"] + pm["m_sensors_kg"] + pm["m_switch_kg"],
                 "ppu_housing_shield": pm["m_housing_kg"] + 0.6, "harness": pm["m_harness_kg"],
                 "thermal": rad["m_thermal_kg"]}
        m_supported = sum(parts.values())
        st = structure_mass(m_supported, span_m=math.sqrt(cfg.intake.area_m2) * 1.1)
        parts["structure"] = st["mass_kg"]
        classes = {"intake": "new", "filter": "new", "compressor": "new", "reservoir": "existing", "feed_valves_lines": "existing",
                   "hall_channel": "modified", "hall_magnetics": "modified", "stage1_hardware": "new", "cathode_assy": "modified",
                   "xe_propellant": "calculated", "xe_tank": "existing", "ppu_converters": "modified", "ppu_control_sensors": "modified",
                   "ppu_housing_shield": "existing", "harness": "calculated", "thermal": "calculated", "structure": "calculated"}
        bom = build_bom(parts, classes)
        # --- replace budgets with engineering values
        P_air = P_bus_steady
        P_peak = P_bus_peak
        m_cbe = bom["cbe_kg"]; m_mev = bom["mev_kg"]; m_mga = bom["mga_kg"]; m_total = m_mev
        checks["power_air"] = P_air <= P_cap; checks["power_peak"] = P_peak <= P_cap
        checks["mass"] = m_mev <= RFP.mass_max_kg
        checks["life"] = all(x["ok"] for x in (L_hall, L_bl, L_mag, L_cat, L_cmp)) and L_int["coating_ok"]
        checks["thermal"] = rad["feasible"]
        hard.append("thermal")
        rfp_compliant = all(checks[k] for k in hard)
        abep_closed = rfp_compliant and checks["net_drag_comp_air"]
        technical_compliant = all(checks[k] for k in technical + ["thermal"])
        technical_closed = technical_compliant and checks["net_drag_comp_air"]
        feasible = rfp_compliant
        eng = {"eng_P_bus_steady_W": P_bus_steady, "eng_P_bus_startup_W": P_bus_start, "eng_P_bus_peak_W": P_bus_peak,
               "eng_ppu_eta": modes["steady"]["eta_overall"], "eng_ppu_loss_W": modes["steady"]["P_loss_W"],
               "eng_ppu_mass_kg": pm["m_ppu_total_kg"], "eng_T_ppu_K": T_ppu, "eng_T_thruster_K": rad["hot"]["T"]["thruster"],
               "eng_T_magnets_K": rad["hot"]["T"]["magnets"], "eng_T_compressor_K": rad["hot"]["T"]["compressor"],
               "eng_T_intake_K": rad["hot"]["T"]["intake"], "eng_T_radiator_K": rad["T_radiator"] if "T_radiator" in rad else rad["hot"]["T_radiator"],
               "eng_A_radiator_m2": rad["A_rad_m2"], "eng_m_thermal_kg": rad["m_thermal_kg"], "eng_thermal_limiting": rad["limiting_node"],
               "eng_P_waste_W": rad["P_waste_W"], "eng_q_aero_W_m2": rad["hot"]["q_aero_W_m2"],
               "eng_life_hall_h": L_hall["life_h"], "eng_hall_wall_remaining_mm_15kh": L_hall["remaining_mm_at_15kh"],
               "eng_intake_coating_erosion_um": L_int["coating_erosion_um"], "eng_intake_alpha_end": L_int["alpha_end"],
               "eng_blade_coating_life_h": L_bl["coating_life_h"], "eng_blade_impact_eV": L_bl["impact_E_eV"],
               "eng_magnet_ok": L_mag["ok"], "eng_cathode_life_h": L_cat["life_evaporation_h"], "eng_cathode_starts": L_cat["starts"],
               "eng_R_15000h": rel["R_15000h"], "eng_R_26000h": rel["R_26000h"], "eng_marginal_items": ",".join(rel["single_point_or_marginal"]),
               "eng_m_cbe_kg": m_cbe, "eng_m_mga_kg": m_mga, "eng_m_mev_kg": m_mev, "eng_structure_t_mm": st["panel_t_mm"],
               "eng_deck_if_own_kg": st["deck_if_own_kg"],
               "eng_xe_tank_kg": tank["mass_kg"], "eng_hall_magnetics_kg": m_mag["mass_kg"], "eng_hall_channel_kg": m_ch,
               "eng_bom": bom["table"]}

    return {
        "architecture": cfg.architecture, "alt_km": cfg.alt_km, "solar": cfg.solar,
        "intake_area_m2": cfg.intake.area_m2, "accommodation": cfg.intake.accommodation,
        "comp_ratio": cfg.compressor.ratio, "vd_V": air["vd_V"],
        "rho": atm["rho"], "fO": atm["fO"], "V_orb": atm["V"], "atm_source": atm["source"],
        "eta_c": col["eta_c"], "C_D": col["C_D"], "intake_model": "tpmc" if cfg.intake.use_tpmc else "parametric",
        "mdot_air_mgps": mdot_air * 1e6, "p_in_Pa": p_in,
        "p_passive_Pa": cmp_["p_passive_Pa"], "passive_ratio": cmp_["passive_ratio"],
        "active_ratio": cmp_["active_ratio"],
        "fO_inlet": inlet["fO"], "fO2_inlet": inlet["fO2"], "O_survival": inlet["O_survival"],
        "ao_flux_m2s": ao["ao_flux"], "ao_fluence_mission_m2": fl,
        "erosion_kapton_um": erosion_depth_um("kapton_HN", fl),
        "erosion_graphite_um": erosion_depth_um("graphite", fl),
        "erosion_silver_um": erosion_depth_um("silver", fl),
        "drag_mN": drag * 1e3, "T_req_mN": T_req * 1e3, "body_area_m2": cfg.body_area_m2,
        "drag_closure_scope": "spacecraft" if cfg.body_area_m2 > 0 else "intake-face only",
        "P_diss_W": air["P_diss_W"], "gaspath_model": "physics" if cfg.gaspath_physics else "parametric", **gas,
        "plasma_model": "physics" if cfg.plasma_physics else "parametric", **plasma,
        "T_air_mN": T_air * 1e3, "Isp_air_s": air["Isp_s"], "eta_u_air": air["eta_u_air"], "I_beam_A": air["I_beam_A"],
        "eta_thr_air": air["eta_thruster"], "T_over_D_air": T_over_D,
        "P_thr_air_W": air["P_thruster_W"], "P_stage1_W": air["P_stage1_W"],
        "P_comp_W": cmp_["comp_power_W"], "P_total_air_W": P_air,
        "xe_peak_mgps": xe_peak * 1e6, "T_peak_mN": peak["T_N"] * 1e3, "P_total_peak_W": P_peak,
        "xe_cathode_kg": xe_cath_kg, "xe_aug_kg": xe_aug_kg, "xe_req_kg": xe_req_kg,
        "xe_total_kg": xe_total_kg,
        "m_thruster_kg": m_thr, "m_ppu_kg": m_ppu, "m_intake_kg": m_intake, "m_comp_kg": m_comp,
        "m_xe_sys_kg": m_xe_sys, "m_struct_kg": m_struct, "m_total_kg": m_total,
        "m_cbe_kg": m_cbe, "m_mga_kg": m_mga, "m_mev_kg": m_mev,
        "chk_mass_mev": m_mev <= RFP.mass_max_kg, "chk_mass_cbe_target": m_cbe <= b.m_cbe_target_kg,
        "ic_thruster": ic_thr, "ic_total": ic_total,
        "life_limit_h": life_h, "life_margin": life_margin,
        "life_limiting": min(life_items, key=life_items.get) if life_items else "none",
        "comp_ratio_effective": cmp_["ratio_effective"],
        "feasible": feasible, "rfp_compliant": rfp_compliant, "abep_closed": abep_closed,
        "technical_compliant": technical_compliant, "technical_closed": technical_closed,
        "engineering_model": "physics" if cfg.engineering_physics else "parametric", **eng,
        **{f"chk_{k}": v for k, v in checks.items()},
    }
