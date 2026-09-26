import pytest as _pt_sup
_SUPERSEDED = _pt_sup.mark.skip(reason="SUPERSEDED: 0-D Hall closure was calibrated with a 2.2-3.2x-low N2 ionisation rate on an invented channel geometry; replaced by HallThruster.jl maps (hallthruster_bridge/). Retired, not expected to pass.")

import numpy as np
import math
from abep_sim import Config, evaluate, CARDS
from abep_sim.atmosphere import atmosphere, orbital_velocity
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.thruster import performance
from abep_sim.constants import G0, E_CHARGE, M_SPECIES


def test_orbital_velocity():
    assert abs(orbital_velocity(200) - 7788) < 5


def test_density_ordering():
    a180 = atmosphere(180, "mean")["rho"]; a230 = atmosphere(230, "mean")["rho"]
    assert a180 > a230
    assert atmosphere(200, "high")["rho"] > atmosphere(200, "low")["rho"]


def test_hall_n2_calibration():
    """Marchioni & Cappelli 2021: ~2 mg/s N2, 17-22 mN, 500-800 W discharge, Isp ~1000 s."""
    atm = {"fO": 0.0, "fN2": 1.0, "fO2": 0.0}
    r = performance(CARDS["hall_1stage"], atm, 2.0e-6, 1.0, vd_V=250)
    assert 14 <= r["T_N"] * 1e3 <= 26
    assert 400 <= r["P_discharge_W"] <= 1000
    assert 700 <= r["Isp_s"] <= 1300


def test_xe_baseline_reasonable():
    atm = {"fO": 0.0, "fN2": 1.0, "fO2": 0.0}
    card = CARDS["hall_1stage"]
    # 1 mg/s Xe anode-only run: Isp ~ 1300-1700 s, T/P ~ 40-60 mN/kW
    r = performance(card, atm, 0.0, 1.0, vd_V=250, mdot_xe_anode=1.0e-6)
    tp = r["T_N"] / r["P_discharge_W"] * 1e6  # mN/kW
    assert 40 <= tp <= 75
    assert 1200 <= r["Isp_s"] <= 1900


def test_closure_independent_of_area():
    """With the intake as the whole ram face, T/D must not depend on area (T and D both ~A)."""
    rs = [evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=a, accommodation=0.5),
                          CompressorParams(ratio=500), vd_V=250))["T_over_D_air"] for a in (0.5, 1.0, 2.0)]
    assert max(rs) - min(rs) < 1e-6
    assert 0 < rs[0] < 1.0   # single-stage Hall never closes on air alone


def test_power_cap_enforced():
    cfg = Config("ecr_gridless", 180, "high", IntakeParams(area_m2=3.0), CompressorParams(ratio=500))
    r = evaluate(cfg)
    assert r["feasible"] is False or r["P_total_peak_W"] <= 1500


def test_passive_floor_on_outlet_pressure():
    """Requested CR below the passive ratio must not lower the reported outlet pressure."""
    from abep_sim.intake import compress, passive_compression
    atm = atmosphere(200, "mean")
    c_lo = compress(CompressorParams(ratio=50.0), atm, 1e-6, 0.4)
    c_pa = compress(CompressorParams(ratio=1.0), atm, 1e-6, 0.4)
    assert abs(c_lo["p_out_Pa"] - c_pa["p_out_Pa"]) < 1e-12
    assert c_lo["active_ratio"] == 1.0 and c_lo["comp_power_W"] == 0.0


def test_hard_gate_includes_12mN_on_air():
    r = evaluate(Config("hall_1stage", 230, "low", IntakeParams(area_m2=0.5), CompressorParams(ratio=500)))
    assert r["chk_thrust_air_ge_req"] is False and r["rfp_compliant"] is False


def test_classification_hierarchy():
    """abep_closed ⊆ rfp_compliant ⊆ technical_compliant; technical_closed ⊆ technical_compliant."""
    r = evaluate(Config("hall_ecr", 180, "mean", IntakeParams(area_m2=0.5, accommodation=0.3), CompressorParams(ratio=2000), vd_V=300))
    assert (not r["abep_closed"]) or r["rfp_compliant"]
    assert (not r["rfp_compliant"]) or r["technical_compliant"]
    assert (not r["technical_closed"]) or r["technical_compliant"]
    assert r["technical_closed"] and not r["abep_closed"]      # closes on physics, blocked only by IC prior


def test_abep_closed_implies_rfp_compliant():
    import itertools
    for arch, area in itertools.product(["hall_1stage", "hall_ecr"], [0.5, 1.0]):
        r = evaluate(Config(arch, 180, "mean", IntakeParams(area_m2=area, accommodation=0.3), CompressorParams(ratio=2000), vd_V=300))
        assert (not r["abep_closed"]) or r["rfp_compliant"]


def test_monte_carlo_runs_and_restores_priors():
    from abep_sim.uncertainty import monte_carlo
    from abep_sim import aochem
    g0 = aochem.RECOMB_GAMMA["stainless_steel"]; eu0 = CARDS["hall_ecr"].eta_u_max["air"]
    d = {"architecture": "hall_ecr", "alt_km": 180, "solar": "mean", "intake_area_m2": 0.5, "comp_ratio": 2000, "vd_V": 300}
    mc = monte_carlo(d, n=30, seed=3)
    assert len(mc) == 30 and mc.T_over_D.between(0.2, 2.0).all()
    assert aochem.RECOMB_GAMMA["stainless_steel"] == g0 and CARDS["hall_ecr"].eta_u_max["air"] == eu0


def test_dissociation_sink_is_consumed():
    from abep_sim.aochem import inlet_composition, AOParams
    atm = atmosphere(200, "mean")
    inl = inlet_composition(atm, AOParams())
    atm_in = {**atm, "fO": inl["fO"], "fN2": inl["fN2"], "fO2": inl["fO2"], "diss_sink_J_per_kg": inl["diss_sink_J_per_kg"]}
    r = performance(CARDS["hall_1stage"], atm_in, 1.0e-6, 0.05, vd_V=250)
    r0 = performance(CARDS["hall_1stage"], {**atm_in, "diss_sink_J_per_kg": 0.0}, 1.0e-6, 0.05, vd_V=250)
    assert r["P_diss_W"] > 0 and r["P_discharge_W"] > r0["P_discharge_W"]


def test_conductance_mode_sets_pressure_from_throughput():
    from abep_sim.intake import compress
    atm = atmosphere(200, "mean")
    c = compress(CompressorParams(anode_conductance_m3_s=0.05), atm, 1.0e-6, 0.4)
    # Q = (mdot/m) k T = p C  -> p = mdot k T / (m C)
    p_expected = 1.0e-6 * 1.380649e-23 * 350.0 / (atm["m_mean"] * 0.05)
    assert abs(c["p_out_Pa"] - max(p_expected, c["p_passive_Pa"])) / c["p_out_Pa"] < 1e-9


def test_threshold_reoptimisation_runs():
    from abep_sim.thresholds import threshold_map
    d = {"architecture": "hall_ecr", "alt_km": 180, "solar": "mean", "intake_area_m2": 0.5, "comp_ratio": 2000, "vd_V": 300}
    df = threshold_map(d, eta_cs=(0.50,), gains=(0.25,), n=40, areas=(0.4, 0.5), vds=(250, 300))
    assert len(df) == 1 and 0.0 <= df.P_closed.iloc[0] <= 1.0 and df.area.iloc[0] in (0.4, 0.5)


def test_msis_in_use_when_available():
    try:
        import pymsis  # noqa
    except ImportError:
        return
    assert atmosphere(200, "mean")["source"].startswith("NRLMSIS")


def test_mission_uq_small_run():
    from abep_sim.mission_uq import mission_closure
    df, s = mission_closure("hall_ecr", 200, 0.5, 2000, 300, n=4, dt_h=24.0, fixed={"eta_c_eff": 0.5, "ecr_gain": 0.25})
    assert len(df) == 4 and 0 <= s["P_mission_closed"] <= 1 and s["m_mev_p50"] > s["m_cbe_p50"]


def test_mass_cbe_mev_reported():
    r = evaluate(Config("hall_ecr", 200, "mean", IntakeParams(area_m2=0.5), CompressorParams(ratio=2000), vd_V=300))
    assert r["m_mev_kg"] == r["m_cbe_kg"] + r["m_mga_kg"] and r["m_mga_kg"] > 0


def test_prior_provenance_and_measurement_override():
    from abep_sim.uncertainty import DEFAULT_PRIORS, set_measured, provenance_table
    t = provenance_table(); assert set(t.fidelity) <= {"analytical", "literature", "breadboard", "qualified"}
    new = set_measured(DEFAULT_PRIORS, "eta_c_specular", 0.42, 0.47, 0.52, "IIST DSMC + AO coupon run 3", "PDR1-INT-003")
    p = next(x for x in new if x.name == "eta_c_specular")
    assert p.fidelity == "breadboard" and p.test_id == "PDR1-INT-003" and p.mode == 0.47


def test_tpmc_limits():
    from abep_sim.intake_tpmc import IntakeGeometry, intake_response
    atm = atmosphere(200, "mean")
    spec = intake_response(IntakeGeometry(area_m2=0.5, L_over_d=10, phi=0.85), atm, 0.0, 0.0, n=6000)
    diff = intake_response(IntakeGeometry(area_m2=0.5, L_over_d=10, phi=0.85), atm, 1.0, 0.0, n=6000)
    assert abs(spec["eta_c"] - 0.85) < 0.01 and abs(spec["K_back"] - 1.0) < 0.01     # specular channel: transparent both ways
    assert diff["eta_c"] < spec["eta_c"] and diff["K_back"] < 0.2 and diff["CR_passive"] > spec["CR_passive"]
    assert 1.9 < spec["C_D"] < 2.2 and 1.9 < diff["C_D"] < 2.2
    tilt = intake_response(IntakeGeometry(area_m2=0.5, L_over_d=10, phi=0.85), atm, 0.3, 10.0, n=6000)
    assert tilt["eta_c"] < intake_response(IntakeGeometry(area_m2=0.5, L_over_d=10, phi=0.85), atm, 0.3, 0.0, n=6000)["eta_c"]


def test_orbit_atmosphere_runs():
    try:
        import pymsis  # noqa
    except ImportError:
        return
    from abep_sim.orbit_atm import orbit_atmosphere
    df, s = orbit_atmosphere(200, n_points=12)
    assert len(df) == 12 and 7700 < s["V_rel_mean"] < 8000 and s["Kn_mean"] > 100
    assert abs(s["fO"] + s["fN2"] + s["fO2"] + s["fN"] + s["fHe"] + s["fH"] + s["fAr"] - 1.0) < 0.05


def test_materials_db_physics():
    from abep_sim.materials import DB, surface_ageing_alpha
    assert DB["SS316"].gamma_O(350) > DB["Al2O3_anodised"].gamma_O(350) > DB["Quartz"].gamma_O(350)
    assert DB["SS316"].gamma_O(450) > DB["SS316"].gamma_O(300)
    assert DB["BN"].sputter_yield(20) == 0.0 and DB["BN"].sputter_yield(300) > DB["BN"].sputter_yield(100) > 0
    assert 0.3 < surface_ageing_alpha(0.3, 0.0) < 0.31 and surface_ageing_alpha(0.3, 1e28) > 0.9


def test_compressor_pumping_speed_limit():
    """Below S = Q/p the machine cannot compress; above it, heavy species compress more than O."""
    from abep_sim.compressor import DragCompressor
    md = {"O": 0.45e-6, "N2": 0.50e-6, "O2": 0.05e-6}
    small = DragCompressor(turbo_area_m2=0.05, turbo_radius_m=0.12, rotor_material="Ti6Al4V").size_for(0.005, md, 5)
    big = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP").size_for(0.005, md, 5)
    assert not small["sized"] and big["sized"]
    assert big["CR_by_species"]["N2"] > big["CR_by_species"]["O"] and big["rotor_ok"]


def test_reservoir_mass_conservation_and_recombination():
    from abep_sim.reservoir import Reservoir
    md = {"O": 0.4e-6, "N2": 0.5e-6, "O2": 0.1e-6}
    for mat in ("SS316", "Al2O3_anodised"):
        s = Reservoir(wall_material=mat, upstream_material=mat).steady_state(md)
        tot_out = sum(s["mdot_anode"].values()) + sum(s["mdot_leak"].values())
        assert abs(tot_out - 1.0e-6) / 1.0e-6 < 1e-6            # mass conserved incl. O->O2
        assert abs(s["mdot_anode"]["N2"] + s["mdot_leak"]["N2"] - 0.5e-6) / 0.5e-6 < 1e-6
    assert Reservoir(wall_material="SS316", upstream_material="SS316").steady_state(md)["O_survival"] < \
        Reservoir(wall_material="Al2O3_anodised", upstream_material="Al2O3_anodised").steady_state(md)["O_survival"]


def test_gaspath_physics_path_runs():
    r = evaluate(Config("hall_ecr", 200, "mean", IntakeParams(area_m2=0.5, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=300, gaspath_physics=True))
    assert r["gaspath_model"] == "physics" and r["comp_sized"] and 0.03 < r["p_in_Pa"] < 0.2 and r["O_survival"] > 0.5


def test_global_plasma_model_behaviour():
    from abep_sim.plasma_chem import Chamber, solve_global
    md = {"O": 0.4e-6, "N2": 0.5e-6, "O2": 0.1e-6}
    lo = solve_global(Chamber(magnetised_wall_factor=0.3), md, 100, f_cutoff_Hz=2.45e9)
    hi = solve_global(Chamber(magnetised_wall_factor=0.3), md, 250, f_cutoff_Hz=2.45e9)
    assert 0 < lo.util_total < hi.util_total < 1 and lo.Te_eV > 3
    assert 100 < hi.eV_per_usable_ion < 600
    tot = sum(hi.power.values()); assert abs(tot - hi.P_abs_W) / hi.P_abs_W < 0.05   # energy accounted
    assert hi.overdense_ratio > 1.0                                                  # 2.45 GHz is overdense here


@_SUPERSEDED
def test_hall_calibration_marchioni_and_spt100():
    from abep_sim.plasma_devices import HallChannel
    r = HallChannel().run(250.0, {"N2": 2.0e-6}, {})
    isp = r["T_N"] / (2e-6 * 9.80665)
    assert 12 <= r["T_N"] * 1e3 <= 30 and 400 <= r["P_d_W"] <= 900 and 800 <= isp <= 1500
    x = HallChannel(L_m=0.025, r_in_m=0.035, r_out_m=0.05, L_iz_frac=0.5).run(300.0, {"Xe": 5.0e-6}, {})
    assert 70 <= x["T_N"] * 1e3 <= 110 and 0.85 <= x["util_hall"] <= 1.0


def test_hall_sustainment_threshold_drops_with_channel_length():
    from abep_sim.plasma_devices import HallChannel
    def thr(L):
        for md in (0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
            f = {"O": 0.43 * md * 1e-6, "N2": 0.49 * md * 1e-6, "O2": 0.08 * md * 1e-6}
            if HallChannel(L_m=L).run(300.0, f, {})["I_beam_A"] > 0.05:
                return md
        return 99
    assert thr(0.20) < thr(0.10)


def test_cathode_shielding_and_coupling_gates():
    from abep_sim.plasma_devices import LaB6Cathode, ECRSource, RFSource
    a = LaB6Cathode(shield_attenuation=1e-3).operate(3.0, 1e-3); b = LaB6Cathode(shield_attenuation=1.0).operate(3.0, 1e-3)
    assert a["coverage"] < b["coverage"] and a["T_emitter_K"] < b["T_emitter_K"]
    assert ECRSource().absorbed(0.05)[1] > ECRSource().absorbed(0.0005)[1]
    assert RFSource().absorbed(0.2, 3e17)[1] > RFSource().absorbed(0.01, 3e17)[1] * 5


def test_full_physics_chain_runs_and_hall_only_can_close():
    r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=300, gaspath_physics=True, plasma_physics=True, hall_L_m=0.20))
    assert r["plasma_model"] == "physics" and r["pl_sustained"] and r["T_over_D_air"] > 1.0


def test_thermal_network_energy_balance_and_sizing():
    from abep_sim.thermal import default_nodes, size_radiator, solve_network, ThermalParams, SIGMA
    atm = atmosphere(200, "mean")
    nodes = default_nodes(600, 1.8, 300, 0, 0.65, 15, 45, 40, 0.7)
    rad = size_radiator(nodes, ThermalParams(), atm["rho"], atm["V"])
    assert rad["feasible"] and all(rad["hot"]["T"][n.name] <= n.T_max_K + 0.5 for n in nodes)
    assert rad["cold"]["T_radiator"] < rad["hot"]["T_radiator"]


def test_ppu_maps_and_modes():
    from abep_sim.ppu import default_ppu, load_modes
    ppu = default_ppu(300, 3.0, False, "", 0, 20)
    m = load_modes(ppu, 2.2, 1.0, 1.5, 0, 15)
    assert 0.85 < m["steady"]["eta_overall"] < 0.985 and m["startup"]["P_bus_W"] > 0
    assert ppu.mass(900)["m_ppu_total_kg"] > 5.0        # redundant space PPU is not light


def test_life_orderings():
    from abep_sim.life import LifeInputs, hall_channel_life, blade_life, cathode_life
    a = hall_channel_life(LifeInputs(hall_wall_thickness_mm=4)); b = hall_channel_life(LifeInputs(hall_wall_thickness_mm=6))
    assert b["life_h"] > a["life_h"]
    assert blade_life(LifeInputs(blade_coating_um=50))["coating_life_h"] > blade_life(LifeInputs(blade_coating_um=20))["coating_life_h"]
    assert cathode_life(LifeInputs(cathode_T_K=1700))["life_evaporation_h"] > cathode_life(LifeInputs(cathode_T_K=1900))["life_evaporation_h"]


def test_full_engineering_chain_bom_consistent():
    r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                        CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, plasma_physics=True, engineering_physics=True,
                        hall_L_m=0.20, hall_shielding=0.03, hall_wall_mm=6.0, blade_coating_um=50, xe_aug_hours=500))
    assert r["engineering_model"] == "physics"
    assert abs(sum(c for _, c, _, _, _ in r["eng_bom"]) - r["eng_m_cbe_kg"]) < 0.05   # table rounded to 2 dp
    assert r["eng_m_mev_kg"] > r["eng_m_cbe_kg"] and r["eng_P_bus_peak_W"] >= r["eng_P_bus_steady_W"]
    assert 0 < r["eng_R_26000h"] < 1


def test_phase5_environment_models():
    from abep_sim.mission_env import Spacecraft, spacecraft_drag, sso_inclination_deg, eclipse_fraction, pointing_factors
    from abep_sim.radiation import RadEnv, electronics_margins, debris_puncture, uv_contamination_ageing
    assert 96.0 < sso_inclination_deg(200) < 96.6
    assert eclipse_fraction(200, 0) > eclipse_fraction(200, 60) > eclipse_fraction(200, 80) == 0.0
    atm = atmosphere(200, "mean")
    d1 = spacecraft_drag(Spacecraft(pointing_sigma_deg=0.5), atm["rho"], atm["V"], 0.7, 2.05)
    d3 = spacecraft_drag(Spacecraft(pointing_sigma_deg=3.0), atm["rho"], atm["V"], 0.7, 2.05)
    assert d3["D_total_N"] > d1["D_total_N"] and d1["D_intake_N"] / d1["D_total_N"] < 0.9
    env = RadEnv(); assert env.tid_krad(0.5) > env.tid_krad(2.0) > env.tid_krad(5.0) > 0
    em = electronics_margins(env, 2.0); assert em["devices"]["gan_fet"]["tid_margin"] > em["devices"]["mcu_cots_screened"]["tid_margin"] > 0
    assert 0 < debris_puncture(0.7, 26000)["P_at_least_one"] < 0.01
    assert uv_contamination_ageing(26000)["alpha_s_end"] > 0.15


def test_phase5_mission_runs_fast_and_reports():
    from abep_sim.mission5 import run_phase5
    from abep_sim.mission_env import Spacecraft
    c = Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
               CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, plasma_physics=True, engineering_physics=True,
               hall_L_m=0.20, hall_shielding=0.03, hall_wall_mm=6.0, blade_coating_um=50, xe_aug_hours=500)
    r = run_phase5(c, Spacecraft(bus_frontal_m2=0.10, array_area_m2=3.5, pointing_sigma_deg=0.5), hours=1000, dt_h=6.0)
    assert set(["mission_closed", "limiting", "tid_krad", "R_26000h", "D_intake_frac"]) <= set(r)
    assert 0.3 < r["D_intake_frac"] < 1.0 and r["tid_krad"] > 0


def test_phase6_sampling_and_conservation():
    from abep_sim.uq6 import sample_correlated, evaluate_full, PRIORS6
    X = sample_correlated(200, seed=2)
    assert abs(X.alpha0.corr(np.log10(X.phi_c))) > 0.4          # surface group correlated
    Xi = sample_correlated(200, seed=2, independent=True)
    assert abs(Xi.alpha0.corr(np.log10(Xi.phi_c))) < 0.25
    r = evaluate_full({"area": 0.7, "L_ch": 0.20, "vd": 275.0, "xe_aug_h": 500, "arch": "hall_1stage"})
    assert r["chk_conservation"] and r["cons_charge_resid"] < 0.03 and r["TD_sc_end"] <= r["TD_sc_start"]


def test_phase6_pareto_and_assimilation_run():
    from abep_sim.uq6 import pareto, assimilate, PRIORS6
    pf = pareto(n_designs=12, seed=9)
    assert len(pf) >= 8 and pf.pareto.sum() >= 1
    new, post = assimilate({"area": 0.7, "L_ch": 0.20, "vd": 275.0, "xe_aug_h": 500, "arch": "hall_1stage"},
                           [{"key": "T_air_mN", "value": 17.5, "sigma": 3.0}], n=20, seed=4)
    assert len(new) == len(PRIORS6)


def test_archengine_enumeration_and_closure():
    from abep_sim.archengine import enumerate_architectures, run_all, gas_path_state, arch_name
    archs = enumerate_architectures()
    names = [arch_name(a) for a in archs]
    assert "hall_internal+hall+lab6_xe" in names and "ecr+grids+lab6_xe" in names and "ecr+mag_nozzle" in names
    assert not any(a["valid"] for a in archs if a["accelerator"].family in ("feep", "electrospray", "ppt"))
    assert not any(arch_name(a) == "hall_internal+mag_nozzle" for a in archs)          # incompatible interface
    from abep_sim.archengine import close_architecture, DesignConstraints, make_gas_fn
    from abep_sim.mission_env import Spacecraft
    gf = make_gas_fn(); gv = {"area": [0.7], "p_level": ["nominal"]}
    sc = Spacecraft(bus_frontal_m2=0.10, array_area_m2=5.0, pointing_sigma_deg=0.5)
    pick = {arch_name(a): a for a in archs}
    hall = close_architecture(pick["hall_internal+hall+lab6_xe"], gf, sc, DesignConstraints(P_bus_max_W=1500), gas_vars=gv)
    grids = close_architecture(pick["ecr+grids+lab6_xe"], gf, sc, DesignConstraints(P_bus_max_W=1500), gas_vars=gv)
    # v1.5: with species-resolved grid optics, grids can out-thrust a sub-threshold Hall at small intakes;
    # the robust difference is life (CEX with unionised air)
    assert hall["feasible"] and grids["feasible"] and hall["life_sys_h"] > grids["life_sys_h"]
    assert grids["life_limiting"] == "grids"                    # the accel grid, not another component, limits life


def test_archengine_v2_interfaces_and_cathode_closure():
    from abep_sim.archengine import enumerate_architectures, arch_name, NEUTRALIZERS, DesignConstraints, rfp_preset
    names = [arch_name(a) for a in enumerate_architectures()]
    assert "hall_internal+mpd" not in names and "self+mpd" in names and "self+pit" in names and "hall_internal+hall+lab6_xe" in names
    mw = [n for n in NEUTRALIZERS if n.name == "mw_air"][0]
    a = mw.operate(0.5, 1e-3); b = mw.operate(3.0, 1e-3)
    assert a["ok"] and not b["ok"] and 0.6 < a["I_max_A"] <= 1.0         # validated ceiling: AMPCAT-class ~0.8-1 A, not 3 A
    assert b["I_max_predicted_A"] > b["I_max_A"]                          # prediction reported separately from validation
    dc = rfp_preset(); assert dc.T_max_mN == 25.0 and dc.T_min_mN == 12.0


@_SUPERSEDED
def test_archengine_v2_nested_optimisation_hall():
    from abep_sim.archengine import enumerate_architectures, close_architecture, make_gas_fn, DesignConstraints, arch_name
    from abep_sim.mission_env import Spacecraft
    gf = make_gas_fn()
    a = [x for x in enumerate_architectures() if arch_name(x) == "hall_internal+hall+lab6_xe"][0]
    r = close_architecture(a, gf, Spacecraft(bus_frontal_m2=0.10, array_area_m2=5.0, pointing_sigma_deg=0.5), DesignConstraints(P_bus_max_W=1500), gas_vars={"area": [0.7], "p_level": ["nominal"]})
    # v1.3 consistent (n_e, T_e) Hall physics: at 0.7 m2 / 1.5 kW the design point exists but does not close the spacecraft
    assert r["feasible"] and 0.3 < r["T_over_D_sc"] < 1.3 and r["n_eval"] >= 9
    assert r["life_limiting"] in ("hall_channel", "blade_coating", "neutralizer") and r["calibration"] in ("interpolation", "extrapolation")
    assert r["thrust_max_ok"] is True or r["thrust_max_ok"] is False        # separate min/max flags exist


def test_v12_branches_execute_and_constraints_bind_inside_search():
    from abep_sim.archengine import enumerate_architectures, close_architecture, make_gas_fn, DesignConstraints, arch_name
    from abep_sim.mission_env import Spacecraft
    sc = Spacecraft(bus_frontal_m2=0.10, array_area_m2=5.0, pointing_sigma_deg=0.5); gf = make_gas_fn()
    pick = {arch_name(a): a for a in enumerate_architectures()}
    gv = {"area": [0.7], "p_level": ["nominal"]}
    assert close_architecture(pick["self+resistojet"], gf, sc, DesignConstraints(1500), gas_vars=gv, strict=True)["status"] == "OK"
    arc = close_architecture(pick["arc+arcjet"], gf, sc, DesignConstraints(1500), gas_vars=gv, strict=True)
    assert arc["status"] == "INFEASIBLE" and "envelope" in arc["reason"]          # pressure envelope, not a crash
    r = close_architecture(pick["hall_internal+hall+lab6_xe"], gf, sc, DesignConstraints(1500, None, 12, 25, None), gas_vars=gv)
    assert r["status"] == "OK" and r["T_mN"] <= 25.0 + 1e-9                         # T_max enforced inside the search
    m = close_architecture(pick["hall_internal+hall+mw_air"], gf, sc, DesignConstraints(1500), gas_vars=gv)
    assert (m["status"] != "OK") or m["I_neut_req_A"] <= m["I_neut_max_A"] + 1e-9   # cathode current closed if OK


@_SUPERSEDED
def test_v12_hall_cex_uses_neutral_velocity_and_ratings_enforced():
    from abep_sim.plasma_devices import HallChannel, hall_fixed_points
    from abep_sim.ppu import PPU, Converter
    f = {"O": 0.42e-6, "N2": 0.51e-6, "O2": 0.07e-6}
    r = HallChannel(L_m=0.25).run(300.0, f, {})
    assert 0.01 < r["f_cx"] < 0.3                       # neutral-velocity CEX: percent-level, not 1e-3
    fp = hall_fixed_points(HallChannel(L_m=0.25), 300.0, f)
    assert fp["has_upper_branch"] and fp["ignites_from_keeper"]
    fp2 = hall_fixed_points(HallChannel(L_m=0.12), 300.0, {k: v * 0.7 for k, v in f.items()})
    assert not fp2["has_upper_branch"]
    ppu = PPU(converters=[Converter("aux", 5.0, 3.0, "aux", redundant=False)])
    assert not ppu.loads({"aux": 8.0})["rating_ok"] and ppu.loads({"aux": 2.0})["rating_ok"]



def test_v13_frozen_surface_is_shipped_and_hashed():
    import json, hashlib, os
    from abep_sim.intake_tpmc import frozen_surface_path
    p = frozen_surface_path(); meta = json.load(open(p.replace(".csv", ".json")))
    assert hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] == meta["sha256_16"]
    assert meta["max_unresolved"] < 1e-3 and set(meta["species"]) == {"O", "N2", "O2"} and "cll" in meta["scattering"]


@_SUPERSEDED
def test_v13_coupled_hall_anchor_monotonic_and_topology():
    from abep_sim.plasma_devices import coupled_channel, hall_run_coupled
    r = hall_run_coupled(coupled_channel(), 250.0, {"N2": 2e-6})
    isp = r["T_N"] / (2e-6 * 9.80665)
    assert 17 <= r["T_N"] * 1e3 <= 26 and 600 <= r["P_d_W"] <= 1000 and 900 <= isp <= 1300 and 20 <= r["Te_eV"] <= 45
    T = []
    for sc in (0.9, 1.0, 1.1, 1.2):
        md = 1.3 * sc
        T.append(hall_run_coupled(coupled_channel(L_m=0.20), 275.0, {"O": 0.43 * md * 1e-6, "N2": 0.51 * md * 1e-6, "O2": 0.06 * md * 1e-6})["T_N"])
    assert all(b >= a * 0.98 for a, b in zip(T, T[1:]))                      # smooth, (near-)monotonic in flow
    f = {"O": 0.43e-6, "N2": 0.51e-6, "O2": 0.06e-6}
    assert hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f)["T_N"] > hall_run_coupled(coupled_channel(L_m=0.10), 275.0, f)["T_N"]
    seeded = hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f, {"O+": 0.17, "N2+": 0.10, "O2+": 0.03})["T_N"]
    assert seeded > hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f)["T_N"]


def test_v13_array_sizing_and_mission_cap():
    from abep_sim.mission_env import Spacecraft, array_area_for, worst_eclipse_fraction
    sc = Spacecraft()
    assert 0.25 < worst_eclipse_fraction(sc, 200.0) < 0.40
    assert array_area_for(1000, sc) > array_area_for(700, sc) and array_area_for(5000, sc) == array_area_for(1500, sc)


def test_v131_plasma_source_and_interstage_conserve_mass():
    import math
    from abep_sim.plasma_chem import Chamber, solve_global, M_ION, M_NEUT
    from abep_sim.constants import E_CHARGE, K_B
    md = {"O": 0.40e-6, "N2": 0.50e-6, "O2": 0.10e-6}
    for P in (100, 300):
        ch = Chamber(magnetised_wall_factor=0.3, volume_m3=1e-3, wall_area_m2=0.06)
        st = solve_global(ch, md, P)
        cbar = {s: math.sqrt(8 * K_B * ch.T_gas_K / (math.pi * M_NEUT[s])) for s in M_NEUT}
        neut = sum(st.n_neut.get(s, 0) * ch.exit_neutral_K * ch.exit_area_m2 * cbar[s] / 4 * M_NEUT[s] for s in ("O", "O2", "N2", "N"))
        ions = sum(st.ion_exit_A[i] / E_CHARGE * M_ION[i] for i in st.ion_exit_A)
        assert abs((neut + ions) / sum(md.values()) - 1) < 0.01


def test_v131_modular_uq_runs():
    from abep_sim.uq_modular import run_uq
    df, s = run_uq("hall_internal+hall+lab6_xe", {"Vd": 300.0, "L_ch": 0.20}, 1.0, 0.05, 6.0, 1500.0, n=6)
    assert len(df) == 6 and 0 <= s["P_close"] <= 1 and "alpha_anom" in df


def test_v14_compressor_leak_self_consistent_and_startup():
    from abep_sim.compressor import DragCompressor
    from abep_sim.reservoir import Reservoir, size_orifice_for_pressure, startup_transient
    md = {"O": 0.45e-6, "N2": 0.50e-6, "O2": 0.05e-6}
    c = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP", leak_conductance_m3_s=2.0)
    c.turbo_rows, c.n_stages, c.rpm = 3, 0, 10000
    a = c.run(0.008, md, self_consistent=False); b = c.run(0.008, md, self_consistent=True)
    assert b["recirculation_frac"] > 0 and b["CR_active"] <= a["CR_active"] + 1e-9           # large leak lowers the ratio
    assert abs(sum(b["delivered_kgps"].values()) - 1.0e-6) < 1e-12                            # steady-state outflow = captured
    res = Reservoir(); size_orifice_for_pressure(res, md, 0.05)
    st = startup_transient(res, md, 0.045, spinup_s=60)
    assert st["t_ignite_s"] is not None and 30 < st["t_ignite_s"] < 60 and st["tau_s"] < 1.0


def test_v14_pareto_and_dedupe():
    import pandas as pd
    from abep_sim.archengine import pareto_front, dedupe_designs
    c = [{"architecture": "a", "area": 1.0, "Vd": 300, "T_mN": 10, "P_bus_W": 1000, "env_ratio": 1.1, "m_system_kg": 50, "life_h": 2e4, "xe_kg": 5},
         {"architecture": "a", "area": 1.0, "Vd": 300, "T_mN": 10, "P_bus_W": 1000, "env_ratio": 1.1, "m_system_kg": 50, "life_h": 2e4, "xe_kg": 5},
         {"architecture": "b", "area": 1.0, "Vd": 300, "T_mN": 12, "P_bus_W": 1100, "env_ratio": 1.0, "m_system_kg": 60, "life_h": 2e4, "xe_kg": 5}]
    d = dedupe_designs(pd.DataFrame(c)); assert len(d) == 2
    pf = pareto_front(d.to_dict("records")); assert pf.pareto.tolist() == [True, False]


def test_v15_source_guard_rejects_unsustained_plasma():
    from abep_sim import archengine as AE
    gf = AE.make_gas_fn(); gas = gf(0.3, 0.05)
    io = [i for i in AE.IONIZERS if i.name == "ecr"][0]
    flows = {"O": gas["mdot_air"] * gas["fO"], "N2": gas["mdot_air"] * gas["fN2"], "O2": gas["mdot_air"] * gas["fO2"]}
    import pytest
    with pytest.raises(ValueError):
        AE._ion_source_impl(io, flows, gas["p_in"], 1400.0, 1e-2, 0.18)        # huge throat: Te pinned / util > 1
    st, neut = AE._ion_source_impl(io, flows, gas["p_in"], 400.0, 3e-3, None)
    assert st.sustained and 0 < st.util_total < 1


def test_v15_grid_optics_and_nozzle_physics():
    from abep_sim import archengine as AE
    gf = AE.make_gas_fn(); gas = gf(0.7, 0.05)
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    g = AE._propulsion(A["ecr+grids+lab6_xe"], gas, {"P_ion": 800.0, "Vb": 1000.0, "A_grid": 1.2e-2, "gap": 1e-3})
    assert 0.005 < g["T_N"] < 0.05 and g["life_items"]["grids"] < 15000          # CEX-limited accel grid on air
    lo = AE._propulsion(A["ecr+grids+lab6_xe"], gas, {"P_ion": 800.0, "Vb": 1000.0, "A_grid": 1.5e-3, "gap": 1e-3})
    assert lo["life_items"]["grids"] < g["life_items"]["grids"]                   # crossover impingement at low perveance
    AE.NOZZLE_ENERGY_BOUND["on"] = False
    n1 = AE._propulsion(A["ecr+mag_nozzle"], gas, {"P_ion": 700.0, "B0": 0.0875, "R_m": 50.0, "A_throat": 3e-3})
    AE.NOZZLE_ENERGY_BOUND["on"] = True
    n2 = AE._propulsion(A["ecr+mag_nozzle"], gas, {"P_ion": 700.0, "B0": 0.0875, "R_m": 50.0, "A_throat": 3e-3})
    AE.NOZZLE_ENERGY_BOUND["on"] = False
    assert 0 < n1["T_N"] <= n2["T_N"] + 1e-12 < 0.02                             # bound >= Maxwellian, both far short
    assert n1["m_acc"] < 10.0                                                     # magnet sized on the throat region


def test_v15_ledger_supplyless_accelerator():
    from abep_sim import archengine as AE
    from abep_sim.mission_env import Spacecraft
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    r = AE.close_architecture(A["ecr+mag_nozzle"], gf, Spacecraft(bus_frontal_m2=0.10, array_area_m2=5.0), AE.DesignConstraints(2500),
                              gas_vars={"area": [0.5], "p_level": [0.05]})
    assert "energy_ledger" not in (r.get("rejections") or r.get("reason") or "")



def test_v151_grid_life_physics_at_fixed_designs():
    """Gate 2: test grid-life physics at fixed designs, not the argmax of a near-degenerate objective."""
    from abep_sim import archengine as AE
    gf = AE.make_gas_fn(); gas = gf(0.7, "nominal")
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    life = {Vb: AE._propulsion(A["ecr+grids+lab6_xe"], gas, {"P_ion": 800.0, "Vb": Vb, "A_grid": 1.2e-2, "gap": 1e-3})["life_items"]["grids"]
            for Vb in (600.0, 800.0, 1000.0, 1500.0, 2000.0)}
    # perveance window: edge impingement below it (P>1), crossover above it (P<0.3), CEX-limited inside it
    assert life[800.0] > life[1000.0] > life[1500.0]           # CEX regime: sputter energy rises with voltage
    assert life[600.0] < 0.1 * life[800.0] and life[2000.0] < 0.1 * life[1500.0]
    assert 2000 < life[1000.0] < 20000


def test_v151_frozen_atmosphere_matches_live_and_is_default():
    from abep_sim.atmosphere import atmosphere
    a = atmosphere(200, "mean")
    assert "frozen scenario" in a["source"] and isinstance(a["rho"], float)
    try:
        import pymsis  # noqa
    except ImportError:
        return
    b = atmosphere(200, "mean", use_msis=True)
    assert abs(a["rho"] / b["rho"] - 1) < 1e-6


def test_v151_golden_benchmarks_reproduce():
    """Gate 6: the golden cases (full intermediate state) reproduce to 1e-6 on any machine (frozen scenario)."""
    from abep_sim.golden import check
    errs = check()
    assert not errs, "\n".join(errs[:20])


@_SUPERSEDED
def test_v16_calibration_anchor_reproduced():
    from abep_sim.validation import calibration_anchor
    c = calibration_anchor()
    assert 17 <= c["T_mN"] <= 23 and 900 <= c["Isp_s"] <= 1200


import pytest as _pytest


@_pytest.mark.xfail(strict=True, reason="Gate 3: the 0-D coupled Hall model does not transfer to the P5 (Brabston et al. 2025); "
                                         "structural upgrade (quasi-1-D) required. Recorded failure, must turn green before baseline freeze.")
def test_v16_blind_validation_p5_nitrogen():
    from abep_sim.validation import validate_p5
    df, s = validate_p5()
    assert s["Id_mean_abs_err"] < 0.30 and s["frac_T_in_range"] >= 0.6


def test_v17_maxwellian_integrator_matches_closed_form():
    from abep_sim.rate_tables import maxwellian_rate, step_cross_section_rate
    import numpy as np
    E = np.array([0.0, 14.99, 15.0, 1000.0]); s = np.array([0.0, 0.0, 1e-20, 1e-20])
    for Te in (3.0, 10.0, 30.0):
        assert abs(maxwellian_rate(E, s, Te) / step_cross_section_rate(1e-20, 15.0, Te) - 1) < 0.01


def test_v17_itikawa_n2_table_is_authoritative():
    from abep_sim.plasma_chem import k_rate, CHEM_PROVENANCE
    assert "Itikawa" in CHEM_PROVENANCE[("N2", "iz")]
    assert 8.0e-15 < k_rate("N2", "iz", 10.0) < 9.0e-15                 # table value at 3/2 Te = 15 eV


def _synthetic_ensemble():
    """Real layer-1 definition with one synthetic layer-2 member whose id matches the synthetic maps' meta."""
    import copy
    from abep_sim.hall_ensemble import load_ensemble
    e = copy.deepcopy(load_ensemble())
    e["admission_rule"] = "synthetic (tests only)"
    e["members"] = [{"ensemble_member_id": "synthetic", "transport_family": "ScaledGaussianBohm",
                     "transport_parameters": {"anom_scale": 0.0625},
                     "calibration_hypotheses": [{"p5_registration": "L32-anode", "beam_efficiency_reading": "A"}],
                     "evidence_basis": "test", "applicability_domain": "test", "validation_status": "test"}]
    return e


def test_v17_hall_map_loader_enforces_pin_schema_and_bounds(tmp_path):
    import json, numpy as np, pytest
    from abep_sim.hall_map import HallMap, REQUIRED_FIELDS, REQUIRED_META, pinned_commit
    axes = {"Vd": [250.0, 300.0], "mdot_kgps": [1e-6, 2e-6]}
    f = {k: (np.ones((2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
    f["converged"] = [[1, 1], [1, 0]]; f["sustained"] = [[1, 1], [1, 1]]
    meta = {k: "synthetic" for k in REQUIRED_META}
    meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"")
    good = {"meta": meta, "axes": axes, "fields": f}
    p = tmp_path / "m.json"; p.write_text(json.dumps(good))
    m = HallMap(str(p), ensemble=_synthetic_ensemble())              # SYNTHETIC map: tests the loader only
    assert m(Vd=260.0, mdot_kgps=1.2e-6)["trustworthy"] is False    # touches the unconverged node
    q = m(Vd=255.0, mdot_kgps=1.1e-6)
    assert q["wall_life_trustworthy"] is False                       # meta ion_wall_losses is the string "synthetic", not True
    with pytest.raises(ValueError):
        m(Vd=350.0, mdot_kgps=1.2e-6)                                # no extrapolation
    bad = dict(good); bad["meta"] = dict(meta, pinned="commit = \"deadbeef\"")
    p2 = tmp_path / "b.json"; p2.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        HallMap(str(p2), ensemble=_synthetic_ensemble())


def test_golden_comparator_near_zero_tolerance():
    """ledger_resid gets an absolute tolerance (round-off vs a stored 0.0); every other key stays relative-only."""
    from abep_sim.golden import _compare
    errs = []
    _compare({"ledger_resid": 0.0}, {"ledger_resid": 1.8e-16}, "c", 1e-6, errs)
    assert not errs
    _compare({"ledger_resid": 0.0}, {"ledger_resid": 1e-9}, "c", 1e-6, errs)
    assert len(errs) == 1
    errs = []
    _compare({"rho": 0.0}, {"rho": 1.8e-16}, "c", 1e-6, errs)   # not in ATOL: still caught
    assert len(errs) == 1


def test_hall_map_schema_v1_shared_by_producer_and_consumer(tmp_path):
    """One schema: hall_map.py derives its fields from it, and run_cases.jl emits exactly the 'computed' ones
    (no placeholders for 'not_computed' fields). Rejects maps without the schema tag."""
    import json, os, re, pytest
    from abep_sim.hall_map import SCHEMA, REQUIRED_FIELDS, HallMap, missing_fields
    root = os.path.dirname(os.path.dirname(__file__))
    src = "".join(open(os.path.join(root, "hallthruster_bridge", f)).read() for f in ("bridge_lib.jl", "run_cases.jl"))
    assert "hall_map_schema_v1.json" in src
    for name, spec in SCHEMA["fields"].items():
        emitted = re.search(rf'"{name}"|:{name}\b', src) is not None
        assert emitted == (spec["status"] == "computed"), (name, spec["status"])
    assert set(missing_fields({k: 0 for k in REQUIRED_FIELDS})) == set()
    assert missing_fields({}) == list(REQUIRED_FIELDS)
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"meta": {"pinned": ""}, "axes": {}, "fields": {}}))
    with pytest.raises(ValueError, match="hall_map_schema_v1"):
        HallMap(str(p))


def test_n_ionization_rate_table_structure():
    """ionization_N.dat (Kim & Desclaux BEB via NIST, scripts/build_n_ionization_table.py): HallThruster.jl format,
    N(4S) threshold, zero at zero energy, non-negative and rising over the Hall range, below N2 (smaller cross section)."""
    import os, numpy as np
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "propellants")
    lines = open(os.path.join(d, "ionization_N.dat")).read().splitlines()
    assert lines[0] == "Ionization energy (eV): 14.534"
    a = np.loadtxt(os.path.join(d, "ionization_N.dat"), skiprows=2)
    b = np.loadtxt(os.path.join(d, "ionization_N2_N2+.dat"), skiprows=2)
    assert a[0, 1] == 0.0 and (a[:, 1] >= 0).all() and a[-1, 0] >= 255
    m = a[:, 0] <= 150
    assert (np.diff(a[m, 1]) > 0).all()
    r = np.interp([15, 30, 60, 150], a[:, 0], a[:, 1]) / np.interp([15, 30, 60, 150], b[:, 0], b[:, 1])
    assert ((r > 0.6) & (r < 0.9)).all()
    assert "Kim & Desclaux" in open(os.path.join(d, "ionization_N.dat.source")).read()


def test_n2_ionization_song2023_table_reproduces_jpcrd_table10():
    """ionization_N2_song2023.dat (Song et al. JPCRD 2023 Table 10, partial sigma(N2+); build script): header 15.58 eV,
    zero below the 16 eV first point, every row equals a fresh integration of the transcribed partial column, the partial
    column never exceeds the total, the tail share is < 1 % over the whole 0-255 eV Hall grid, and n2_n.toml uses it
    (introduced in reaction set abep-n2n-0.2)."""
    import importlib.util, os, tomllib, numpy as np
    from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_ionization_song2023_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    lines = open(os.path.join(d, "ionization_N2_song2023.dat")).read().splitlines()
    assert lines[0] == "Ionization energy (eV): 15.58"
    a = np.loadtxt(os.path.join(d, "ionization_N2_song2023.dat"), skiprows=2)
    assert a[0, 1] == 0.0 and (a[:, 1] >= 0).all() and a[-1, 0] >= 255
    E = np.array([r[0] for r in b.TABLE10], float); sig = np.array([r[1] for r in b.TABLE10]) * 1e-20
    assert len(E) == 57 and E[0] == 16.0 and E[-1] == 1000 and (np.diff(E) > 0).all()
    assert all(r[1] <= r[2] for r in b.TABLE10)
    for eps in (15.0, 30.0, 60.0, 150.0, 255.0):
        row = a[a[:, 0] == eps][0, 1]
        assert abs(row / maxwellian_rate(E, sig, eps / 1.5, b.TAIL) - 1) < 1e-5
    assert all(dd < 0.01 for _, dd in tail_sensitivity(E, sig, [45, 150, 255]))
    cfg = open(os.path.join(d, "n2_n.toml")).read()
    assert '"ionization_N2_song2023.dat"' in cfg and '"ionization_N2_N2+.dat"' not in cfg
    pinned = tomllib.load(open(os.path.join(root, "hallthruster_bridge", "PINNED.toml"), "rb"))["reaction_set"]
    assert any(h.startswith("abep-n2n-0.2") and "ionization_N2_song2023.dat" in h for h in pinned["history"])


def test_n2_elastic_song2023_table_reproduces_jpcrd_table5():
    """elastic_N2_song2023.dat (Song et al. JPCRD 2023 Table 5 momentum-transfer cross section; build script): 40
    transcribed points 0.001 eV-10 keV, each row equals a fresh integration with linear-in-E interpolation, the log-log
    interpolation alternative stays within 3 % over the Hall grid, n2_n.toml uses it, and the reaction set is abep-n2n-0.3
    with one history line per version."""
    import importlib.util, os, tomllib, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_elastic_song2023_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    lines = open(os.path.join(d, "elastic_N2_song2023.dat")).read().splitlines()
    assert lines[0].endswith("(eV): 0.0")
    a = np.loadtxt(os.path.join(d, "elastic_N2_song2023.dat"), skiprows=2)
    E = np.array([r[0] for r in b.TABLE5], float); sig = np.array([r[1] for r in b.TABLE5]) * 1e-20
    assert len(E) == 40 and E[0] == 0.001 and E[-1] == 10000 and (np.diff(E) > 0).all()
    for eps in (3.0, 15.0, 45.0, 150.0, 255.0):
        row = a[a[:, 0] == eps][0, 1]
        assert abs(row / maxwellian_rate(E, sig, eps / 1.5, b.TAIL) - 1) < 1e-5
    assert all(abs(dd) < 0.03 for _, dd in b.interpolation_sensitivity(E, sig, [3, 30, 255]))
    cfg = open(os.path.join(d, "n2_n.toml")).read()
    assert '"elastic_N2_song2023.dat"' in cfg and '"elastic_N2.dat"' not in cfg
    pinned = tomllib.load(open(os.path.join(root, "hallthruster_bridge", "PINNED.toml"), "rb"))["reaction_set"]
    assert any(h.startswith("abep-n2n-0.3") and "elastic_N2_song2023.dat" in h for h in pinned["history"])
    versions = [h.split()[0].rstrip(":") for h in pinned["history"]]
    assert versions == [f"abep-n2n-0.{i}" for i in range(1, len(versions) + 1)] and pinned["version"] == versions[-1]


def test_n2_completeness_audit_preregistration_is_frozen():
    """The omitted-process audit criteria were pre-registered before any P5-N2 scoring. Changing them is a new
    pre-registration (new id), never an edit of v1."""
    import json, os
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "prereg", "n2_completeness_audit_v1.json")
    r = json.load(open(p))
    assert r["id"] == "n2_completeness_audit_v1" and r["registered"] == "2026-09-26"
    assert r["thresholds"] == {"F_P": 0.01, "F_ion": 0.01, "F_S_s": 0.05}
    assert r["domains"]["default"]["Te_eV"] == [2.0, 30.0] and r["domains"]["default"]["mean_energy_eV"] == [3.0, 45.0]
    assert r["domains"]["vibrational_excitation"]["Te_eV"] == [0.2, 30.0]
    assert r["domains"]["rotational_excitation"]["Te_eV"] == [0.2, 30.0]


def test_n2_dissociative_ionization_audit_promotes_under_the_preregistered_rule():
    """Provisional omitted-process audit (prereg n2_completeness_audit_v1): even the LOWER bound on dissociative
    ionization (JPCRD Table 10 sigma(N+ + N2++) as published, energy loss at threshold, one ion per event) exceeds the 1 %
    F_ion and F_P thresholds inside T_e = 2-30 eV, so DI must be promoted. The committed result file matches a re-run."""
    import importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("a", os.path.join(root, "scripts", "audit_n2_dissociative_ionization.py"))
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    res = json.load(open(os.path.join(root, "hallthruster_bridge", "audit", "n2_dissociative_ionization_v1.json")))
    assert res["prereg"] == "n2_completeness_audit_v1" and res["status"].startswith("PROMOTION FINAL (forced by F_ion)")
    assert res["verdict"]["dissociative_ionization"].startswith("PROMOTE")
    assert abs(a.E_TH_DI - 24.284) < 1e-9
    r20 = next(r for r in res["rows"] if r["Te_eV"] == 20.0)
    k_iz = a.table_rate("ionization_N2_song2023.dat", 20.0); k_tab = a.omitted_rate(a.TABLE10_NPLUS, 20.0)
    assert abs(k_tab / k_iz - r20["F_ion_lower"]) < 1e-9 and r20["F_ion_lower"] > 0.01
    assert all(r["F_P_lower"] <= r["F_P_upper"] and r["F_ion_lower"] <= r["F_ion_upper"] for r in res["rows"])


def test_n2_dissociative_ionization_tables_and_chemistry_variants():
    """Dissociative ionization (promoted by the pre-registered audit): header = appearance energy 24.284 eV (no fixed
    kinetic-energy add-on), nominal linear ramp from sigma = 0 at threshold, rows equal a fresh integration, lower <= upper
    everywhere, and the two chemistry-variant configs differ only in that one rate file."""
    import importlib.util, os, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_dissociative_ionization_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    tabs = {}
    for v, f in b.FILES.items():
        lines = open(os.path.join(d, f)).read().splitlines()
        assert lines[0].endswith("(eV): 24.284")
        a = np.loadtxt(os.path.join(d, f), skiprows=2); tabs[v] = a
        E, s = b.cross_section(v)
        assert E[0] == b.E_TH and s[0] == 0.0 and E[1] == 30.0
        for eps in (15.0, 45.0, 150.0):
            assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, s, eps / 1.5, b.TAIL) - 1) < 1e-5
    assert (tabs["lower"][:, 1] <= tabs["upper"][:, 1]).all()
    up = open(os.path.join(d, "n2_n.toml")).read().splitlines()
    lo = open(os.path.join(d, "n2_n_di_lower.toml")).read().splitlines()
    diff = [(x, y) for x, y in zip(up, lo[1:]) if x != y]
    assert lo[0].startswith("# GENERATED VARIANT") and len(up) == len(lo) - 1 and len(diff) == 1
    assert "dissociative_ionization_N2_upper.dat" in diff[0][0] and "dissociative_ionization_N2_lower.dat" in diff[0][1]


def test_n_z1plus_to_z2plus_bell1983_table():
    """ionization_N_Z1plus_to_N_Z2plus.dat (Bell et al. JPCRD 1983 Eq. (1), N II): the transcribed formula gives the values checked on
    2026-09-26 (peak ~0.50e-16 cm^2 near 100-150 eV), Bell's N I row agrees with NIST Kim & Desclaux 30 % mix at 100 eV
    (1.577e-16 cm^2) within 3 %, header = IE(N II), rows equal a fresh integration, and n2_n.toml has N max_charge = 2."""
    import importlib.util, os, tomllib, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n_z1plus_to_z2plus_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    assert abs(b.bell_sigma_m2(100.0) * 1e20 - 0.4995) < 0.001 and abs(b.bell_sigma_m2(150.0) * 1e20 - 0.4944) < 0.001
    assert b.bell_sigma_m2(29.0) == 0.0
    assert abs(b.bell_sigma_m2(100.0, "N I") * 1e20 / 1.577 - 1) < 0.03
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    assert open(os.path.join(d, "ionization_N_Z1plus_to_N_Z2plus.dat")).readline().strip() == "Ionization energy (eV): 29.60125"
    a = np.loadtxt(os.path.join(d, "ionization_N_Z1plus_to_N_Z2plus.dat"), skiprows=2)
    E = b.grid(); s = b.bell_sigma_m2(E)
    for eps in (30.0, 45.0, 150.0):
        assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, s, eps / 1.5, b.TAIL) - 1) < 1e-5
    cfg = tomllib.load(open(os.path.join(d, "n2_n.toml"), "rb"))
    assert next(sp for sp in cfg["species"] if sp["symbol"] == "N")["max_charge"] == 2
    assert any(r.get("equation") == "N(+) + e -> N(2+) + 2e" for r in cfg["reactions"])


def test_n2_to_n_z2plus_table():
    """dissociative_ionization_N2_to_N_Z2plus.dat (Song 2023 Table 10 sigma(N++)): threshold ramp from 53.885 eV, header = that
    appearance energy, rows equal a fresh integration, and n2_n.toml carries the charge-balanced equation."""
    import importlib.util, os, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_to_n_z2plus_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    assert b.E_TH == 53.885
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    assert open(os.path.join(d, "dissociative_ionization_N2_to_N_Z2plus.dat")).readline().strip() == "Ionization energy (eV): 53.885"
    a = np.loadtxt(os.path.join(d, "dissociative_ionization_N2_to_N_Z2plus.dat"), skiprows=2)
    E, s = b.cross_section()
    assert E[0] == 53.885 and s[0] == 0.0 and E[1] == 70.0
    for eps in (30.0, 45.0, 150.0):
        assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, s, eps / 1.5, b.TAIL) - 1) < 1e-5
    assert 'equation = "N2 + e -> N(2+) + N + 3e"' in open(os.path.join(d, "n2_n.toml")).read()


def test_n2_vibrational_audit_promotion_is_robust_at_low_te():
    """Audit 2 (prereg n2_completeness_audit_v1, vibrational domain 0.2-30 eV): Laporta et al. 2014 Eq. (10) with
    kappa_max in 1e-9 cm^3/s (0->1 peaks at ~8.0e-9 cm^3/s near 1.6 eV, matching JPCRD Table 7), and vibrational power
    exceeds 1 % of the inelastic power even with the 8 electronic channels in the denominator at T_e <= 3 eV (robust, not a
    completeness claim: other omitted channels are still being bounded)."""
    import importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("a", os.path.join(root, "scripts", "audit_n2_vibrational_excitation.py"))
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    assert abs(a.k_vib(1.585, 1)[0][1] / 8.015e-15 - 1) < 1e-3
    assert len(a.LAPORTA_V0) == 59 and len(a.EPS_V) == 59 and a.EPS_V[1] == 0.288
    res = json.load(open(os.path.join(root, "hallthruster_bridge", "audit", "n2_vibrational_excitation_v1.json")))
    assert res["prereg"] == "n2_completeness_audit_v1" and res["verdict"]["vibrational_excitation"].startswith("PROMOTION ROBUST")
    fin = [r for r in res["rows"] if r["electronic_in_denominator_trusted"]]
    assert fin[-1]["Te_eV"] == 3.0 and max(r["F_P_vs_included_plus_electronic"] for r in fin) > 0.01


def test_n2_vibrational_tables_use_two_thirds_mean_energy():
    """abep-n2n-0.7: ten tables v=0 -> v_f = 1..10. HallThruster's axis is mean electron energy eps_bar = 3/2 T_e, so the
    row at eps_bar must equal Laporta's Eq. (10) at T_e = 2/3 eps_bar (NOT at T_e = eps_bar). Headers = eps_vf; the omitted
    v_f > 10 tail stays < 1 % of the vibrational power over T_e = 0.2-30 eV; all ten are in n2_n.toml."""
    import importlib.util, os, numpy as np
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_vibrational_tables.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    cfg = open(os.path.join(d, "n2_n.toml")).read()
    for vf in range(1, 11):
        lines = open(os.path.join(d, b.fname(vf))).read().splitlines()
        assert lines[0] == f"Excitation energy (eV): {b.vib.EPS_V[vf]}"
        a = np.loadtxt(os.path.join(d, b.fname(vf)), skiprows=2)
        for eps in (3.0, 15.0, 45.0):
            row = a[a[:, 0] == eps][0, 1]
            assert abs(row / b.vib.k_vib(2 * eps / 3, vf)[0][1] - 1) < 1e-5
            assert abs(row / b.vib.k_vib(eps, vf)[0][1] - 1) > 0.05          # the wrong (T = eps_bar) reading differs
        assert f'"{b.fname(vf)}"' in cfg
    assert max(b.vib_tail_fraction(T) for T in (0.2, 1, 3, 10, 30)) < 0.01


def test_n_elastic_tables_from_ragimkhanov_fig1b():
    """abep-n2n-0.8: atomic-N momentum transfer, vector-extracted from Ragimkhanov et al. 2026 Fig. 1b (CC BY). The
    committed extraction reproduces the calibration anchors (OPM 1-1e6 eV; Wang BSR 0.95-128 eV), the OPM/Wang
    disagreement in the Hall range is carried as a variant (not resolved), and n2_n.toml uses the OPM table."""
    import importlib.util, os, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n_elastic_tables.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = b.load()
    Eo, So = d["opm"]; Ew, Sw = d["wang"]
    assert abs(Eo[0] - 1.0) < 0.01 and abs(Eo[-1] / 1e6 - 1) < 0.01 and abs(Ew[-1] - 128) < 1
    assert 12.5 < np.interp(10.0, Eo, So) < 14.5 and 21 < np.interp(10.0, Ew, Sw) < 24      # a0^2, checked 2026-09-26
    for v, f in b.FILES.items():
        a = np.loadtxt(os.path.join(b.PROP, f), skiprows=2)
        E, s = b.cross_section(v)
        for eps in (3.0, 15.0, 45.0):
            assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, s, eps / 1.5, b.TAIL) - 1) < 1e-5
    r = maxwellian_rate(*b.cross_section("opm"), 5.0) / maxwellian_rate(*b.cross_section("wang"), 5.0)
    assert 0.4 < r < 0.7                                     # material disagreement: carried, not resolved
    assert '"elastic_N_ragimkhanov2026.dat"' in open(os.path.join(b.PROP, "n2_n.toml")).read()
    assert '"elastic_N_wang2014_bsr.dat"' in open(os.path.join(b.PROP, "n2_n_nel_wang.toml")).read()


def test_n2_electronic_excitation_tables_su_johnson_splice():
    """abep-n2n-0.9: eight state-resolved electronic excitations. Su 2021 below 20 eV, Johnson 2005 points exactly (no
    renormalization) from 20 eV, power-law continuation anchored at Johnson's LAST point (value and slope continuous), headers
    = experimental vertical energies, rows = fresh integration, and n2_n.toml now names only files that exist."""
    import importlib.util, os, tomllib, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_electronic_excitation_tables.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    exp = {"A": 7.75, "B": 8.04, "W": 8.88, "Bp": 9.67, "a": 9.31, "ap": 9.92, "w": 10.27, "C": 11.19}
    for key in b.STATES:
        assert b.STATES[key][2] == exp[key]
        E, S = b.cross_section(key)
        Es, Ss = b.su(key); Ej, Sj, _ = b.johnson(key)
        m = E < 20
        assert np.allclose(S[m], np.interp(E[m], Es, Ss))
        for e, s in zip(Ej[Ej >= 20], Sj[Ej >= 20]):
            assert S[E == e][0] == s                                   # Johnson values used exactly
        i = int(np.where(E == Ej[-1])[0][0])
        assert S[i + 1] < S[i] and S[i + 1] / S[i] > 0.9               # continuation starts AT the last point
        lines = open(os.path.join(b.PROP, b.fname(key))).read().splitlines()
        assert lines[0] == f"Excitation energy (eV): {exp[key]}"
        a = np.loadtxt(os.path.join(b.PROP, b.fname(key)), skiprows=2)
        for eps in (15.0, 45.0):
            assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, S, eps / 1.5, "zero") - 1) < 1e-5
        assert b.continuation_sensitivity(key, 30)[0] < 0.1
    cfg = tomllib.load(open(os.path.join(b.PROP, "n2_n.toml"), "rb"))
    files = [r["rate_coeff_file"] for r in cfg["reactions"]]
    assert "excitation_N2.dat" not in files and all(os.path.isfile(os.path.join(b.PROP, f)) for f in files)


def test_n2_completeness_final_audit():
    """Final omitted-process pass on abep-n2n-0.9 (prereg v1): DI and vibrational fractions recomputed on the complete
    denominator; rotational gross bound uses NIST B_0 (0->2 = 1.480 meV, 0->4 = 4.933 meV); N^2+ -> N^3+ excluded on the
    reference state; direct N -> N^2+ and molecular N2^2+ closed by the blind state envelope (promoted / uncertainty variant)."""
    import importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("a", os.path.join(root, "scripts", "audit_n2_completeness_final.py"))
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    assert abs(a.ROT_DE_SPECTRO_EV[1] - 1.480e-3) < 2e-6 and abs(a.ROT_DE_SPECTRO_EV[2] - 4.933e-3) < 5e-6
    v = json.load(open(os.path.join(root, "hallthruster_bridge", "audit", "n2_completeness_final_v1.json")))["verdict"]
    assert v["dissociative_ionization"]["final_F_ion_max"] > 0.01 and v["vibrational_excitation"]["final_F_P_max"] > 0.01
    assert 0.01 < v["rotational_excitation"]["F_P_spectroscopic_max"] < 0.02
    assert v["N_Z2plus_to_N_Z3plus"]["verdict"].startswith("EXCLUDED") and v["N_Z2plus_to_N_Z3plus"]["x_crit_min"] > 0.2
    assert v["N_to_N_Z2plus_direct"]["verdict"].startswith("Closure: PROMOTED")
    assert "UNCERTAINTY VARIANT" in v["N2_Z2plus_molecular"]["verdict"]
    res = json.load(open(os.path.join(root, "hallthruster_bridge", "audit", "n2_completeness_final_v1.json")))
    assert res["status"].startswith("CLOSED")
    m = v["N2_Z2plus_molecular"]
    assert m["F_ion_nominal_max"] < 0.01 < m["F_ion_upper_max"]           # envelope straddles the criterion
    up = open(os.path.join(root, "hallthruster_bridge", "propellants", "n2_n.toml")).read()
    off = open(os.path.join(root, "hallthruster_bridge", "propellants", "n2_n_rot_off.toml")).read()
    assert "_rot_j0_to_j2" in up and "_rot_" not in off


def test_n2_rotational_tables():
    """abep-n2n-0.10: rotational j 0->2 / 0->4 from JPCRD Table 6 with NIST-B_0 headers; rows = fresh integration."""
    import importlib.util, os, numpy as np
    from abep_sim.rate_tables import maxwellian_rate
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_rotational_tables.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    cfg = open(os.path.join(b.PROP, "n2_n.toml")).read()
    for col, f in b.FILES.items():
        assert open(os.path.join(b.PROP, f)).readline().strip() == f"Excitation energy (eV): {round(b.aud.ROT_DE_SPECTRO_EV[col], 7)}"
        a = np.loadtxt(os.path.join(b.PROP, f), skiprows=2); E, s = b.cross_section(col)
        for eps in (2.0, 15.0):
            assert abs(a[a[:, 0] == eps][0, 1] / maxwellian_rate(E, s, eps / 1.5, "hold") - 1) < 1e-5
        assert f'"{f}"' in cfg


def test_johnson_low_sensitivity_branch():
    """Johnson-low branch: Johnson 2005 at all energies with a ramp from the experimental threshold; used only by
    n2_n_exc_johnsonlow.toml, which differs from n2_n.toml in exactly the eight electronic-excitation files."""
    import importlib.util, os, numpy as np
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_electronic_excitation_tables.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    for key in b.STATES:
        E, S = b.cross_section(key, variant="johnsonlow"); Ej, Sj, _ = b.johnson(key)
        assert E[0] == b.STATES[key][2] and S[0] == 0.0 and np.all(np.isin(Ej, E))
        assert os.path.isfile(os.path.join(b.PROP, b.fname(key, "johnsonlow")))
    up = open(os.path.join(b.PROP, "n2_n.toml")).read().splitlines()
    jl = open(os.path.join(b.PROP, "n2_n_exc_johnsonlow.toml")).read().splitlines()[1:]
    diff = [(x, y) for x, y in zip(up, jl) if x != y]
    assert len(up) == len(jl) and len(diff) == 8 and all("_johnsonlow.dat" in y for _, y in diff)


def test_variant_configs_are_regenerated_from_n2_n():
    """Every chemistry-variant config equals what scripts/make_n2_variant_configs.py produces from the current n2_n.toml."""
    import importlib.util, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("m", os.path.join(root, "scripts", "make_n2_variant_configs.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    base = open(os.path.join(m.PROP, "n2_n.toml")).read()
    for name, (what, subs) in m.VARIANTS.items():
        exp = base
        for a, c in subs.items():
            exp = exp.replace(a, c)
        assert open(os.path.join(m.PROP, name)).read().split("\n", 1)[1] == exp, name


def test_completeness_ambiguity_addendum_is_frozen():
    """Addendum 1 to n2_completeness_audit_v1 (registered before the full blind-envelope summary): exclude if upper <
    threshold, promote if lower > threshold, promote as an uncertainty variant if the threshold lies between."""
    import json, os
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "prereg",
                     "n2_completeness_audit_v1_addendum1_ambiguity.json")
    r = json.load(open(p))
    assert r["amends"] == "n2_completeness_audit_v1" and r["registered"] == "2026-09-26"
    assert r["rule"]["upper_bound_below_threshold"] == "EXCLUDE"
    assert r["rule"]["lower_bound_above_threshold"].startswith("PROMOTE")
    assert r["rule"]["threshold_between_lower_and_upper"].startswith("PROMOTE AS AN UNCERTAINTY VARIANT")


def test_completeness_crosscheck_addendum_is_frozen():
    """Addendum 2: earlier/later envelope run sets are an implementation cross-check, never averaged or selected; the newest
    set is authoritative; a verdict-altering discrepancy blocks the completeness rule until resolved."""
    import json, os
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "prereg",
                     "n2_completeness_audit_v1_addendum2_crosscheck.json")
    r = json.load(open(p))
    assert r["amends"] == "n2_completeness_audit_v1" and r["registered"] == "2026-09-26"
    assert "never averaged" in r["rule"]["authoritative_set"]
    assert r["rule"]["discrepancy"].startswith("Any discrepancy")

def test_multiply_charged_tables_and_closure_status():
    """abep-n2n-0.11: every multiply-charged table (bound and propellant) equals a fresh build; HMS = Eqs. (2)+(3) with the
    VizieR N parameters; energy headers close (N: 14.53 + 29.60 = 44.14 eV; N2^2+: both routes give 42.9 eV); the reaction
    set is COMPLETE_FOR_P5_N2_VALIDATION with the audited domain and every listed variant config present."""
    import importlib.util, os, tempfile, filecmp, tomllib, numpy as np
    from abep_sim.rate_tables import write_hallthruster_table
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("m", os.path.join(root, "scripts", "build_multiply_charged_tables.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    with tempfile.TemporaryDirectory() as t:
        for d, name, E, sg, th, src in m.tables():
            p = os.path.join(t, name); write_hallthruster_table(p, E, sg, th, source=src)
            assert filecmp.cmp(p, os.path.join(d, name), shallow=False), name
    assert m.HMS_D == (44.1354, 43.0) and m.HMS_IA == (403.0, 0.9926, 3.6, 5.0)
    u = 2.0; E = np.array([u * 44.1354])
    assert abs(m.hms_sigma(E)[0] / ((1 - np.exp(-3)) * 43 / 44.1354 ** 3 * 1 / 2.5 ** 2 * 1e-17) - 1) < 1e-12
    prop = os.path.join(root, "hallthruster_bridge", "propellants")
    hdr = lambda f: float(open(os.path.join(prop, f)).readline().split(":")[1])
    assert abs(hdr("ionization_N.dat") + hdr("ionization_N_Z1plus_to_N_Z2plus.dat") - hdr("ionization_N_to_N_Z2plus_hms2017.dat")) < 1e-3
    assert abs(hdr("ionization_N2_song2023.dat") + hdr("ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat")
               - hdr("ionization_N2_to_N2_Z2plus_upper.dat")) < 1e-3
    rs = tomllib.load(open(os.path.join(root, "hallthruster_bridge", "PINNED.toml"), "rb"))["reaction_set"]
    assert rs["version"] == "abep-n2n-0.11" and rs["status"] == "COMPLETE_FOR_P5_N2_VALIDATION"
    assert "T_e 2-30 eV" in rs["domain"] and "0.2-30 eV" in rs["domain"]
    for v in rs["uncertainty_variants"]:
        for f in v.split(":")[0].split(" / "):
            assert os.path.exists(os.path.join(prop, f.strip())), f
    cfg = open(os.path.join(prop, "n2_n.toml")).read()
    assert '"ionization_N_to_N_Z2plus_hms2017.dat"' in cfg and "N2(2+)" not in cfg
    dic = open(os.path.join(prop, "n2_n_n2dication.toml")).read()
    assert "N2 + e -> N2(2+) + 3e" in dic and "N2(+) + e -> N2(2+) + 2e" in dic and "dissociative_ionization_N2_lower.dat" in dic

def test_audit_config_snapshots_are_immutable():
    """Historical closure calculations read hash-pinned snapshots (audit/configs/MANIFEST.json), never the mutable production
    TOMLs (PR #25 review P1/P2): each snapshot and every rate table it names match the recorded sha256; the 0.9 snapshot has
    no rotation; the 0.10 snapshots have no assessed multiply-charged process; both closure scripts point at the snapshots."""
    import hashlib, json, os, tomllib
    root = os.path.dirname(os.path.dirname(__file__))
    d = os.path.join(root, "hallthruster_bridge", "audit", "configs"); prop = os.path.join(root, "hallthruster_bridge", "propellants")
    man = json.load(open(os.path.join(d, "MANIFEST.json")))
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    for f, m in man["configs"].items():
        assert h(os.path.join(d, f)) == m["sha256"], f
        cfg = tomllib.load(open(os.path.join(d, f), "rb"))
        assert sorted({r["rate_coeff_file"] for r in cfg["reactions"]}) == sorted(m["rate_files"]), f
        for x, sha in m["rate_files"].items():
            assert h(os.path.join(prop, x)) == sha, (f, x)
        files = " ".join(m["rate_files"])
        assert not any(t in files for t in ("N_to_N_Z2plus", "N_Z2plus_to_N_Z3plus", "N2_to_N2_Z2plus", "N2_Z1plus_to_N2_Z2plus")), f
    assert "rot_j0" not in " ".join(man["configs"]["n2_n_0p9_pre_rotation.toml"]["rate_files"])
    env = open(os.path.join(root, "hallthruster_bridge", "checks", "blind_state_envelope.jl")).read()
    assert env.count("audit/configs/n2_n_0p10_") == 4 and '"propellants/$(cfg)"' not in env
    fa = open(os.path.join(root, "scripts", "audit_n2_completeness_final.py")).read()
    assert '"n2_n_0p9_pre_rotation.toml"' in fa


def test_p5_n2_run_status_rule_is_frozen():
    """Owner decision 2026-09-26: four run statuses; chemistry-untrustworthy runs are OUT_OF_DOMAIN (not FAIL); admission
    needs scoreable runs at every point under the four primary chemistry configs; the f_out = 0 rule is not relaxed."""
    import json, os
    r = json.load(open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "prereg",
                                    "p5_n2_run_status_rule_v1.json")))
    assert list(r["run_status"]) == ["PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE"]
    assert r["candidate_status"]["not_all_mandatory_runs_scoreable"].startswith("INCONCLUSIVE")
    assert r["mandatory_chemistry_for_admission"] == ["n2_n.toml", "n2_n_di_lower.toml", "n2_n_nel_wang.toml",
                                                      "n2_n_di_lower_nel_wang.toml"]
    assert r["chemistry_trust_rule"]["f_out_tolerance"] == 1e-12

def test_p5_n2_measurement_audit_values():
    """P5-N2 measurement audit (Brabston 2025): Table 2 transcribed; I_d raw = P_d/V_d and Eq. (13)-(14) correction recomputed;
    thrust targets from the abstract end-points and Fig. 5; the digitization reproduces the abstract N1/N5 thrust within 0.4 mN
    and the Xe Eq. (14) powers within 5 W; N2 Fig. 9 components reproduce the Fig. 8 component eta_T."""
    import json, math, os, importlib.util
    root = os.path.dirname(os.path.dirname(__file__))
    d = json.load(open(os.path.join(root, "hallthruster_bridge", "identification", "brabston_p5_n2_measurement_audit_v1.json")))
    spec = importlib.util.spec_from_file_location("a", os.path.join(root, "scripts", "audit_p5_n2_measurements.py"))
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    for p, (ma, mc, vd, pd, bg, pr) in a.TABLE2.items():
        v = d["points"][p]
        assert abs(v["I_d_raw_A"] - pd * 1e3 / vd) < 1e-9
        men = a.ingestion(pr, a.M_N2)
        assert abs(v["I_d_corr_eq14_A"] - (pd * 1e3 / vd - men * a.E_CH / a.M_N2)) < 1e-9
        assert v["T_sigma_mN"] == 2.6 and bg == 130
    assert d["points"]["N1"]["T_corr_mN"] == 61.4 and d["points"]["N5"]["T_corr_mN"] == 90.0
    assert abs(d["points"]["N1"]["fig5"]["T_mN"] - 61.4) < 0.4 and abs(d["points"]["N5"]["fig5"]["T_mN"] - 90.0) < 0.4
    assert all(abs(x["P_fig5_kW"] - x["P_eq14_kW"]) < 0.005 for x in d["xenon_calibration_check"])
    fig8 = sorted(b["y"] for b in d["fig8_raw"]["blobs"] if abs(b["V_d"] - 278.6) < 0.5)
    assert abs(d["points"]["N3"]["consistency"]["eta_T_component_from_fig9"] - fig8[0]) < 0.002
    assert abs(d["points"]["N3"]["consistency"]["eta_T_thrust_from_T_Id_corr"] - fig8[1]) < 0.002
    f = json.load(open(os.path.join(root, "hallthruster_bridge", "identification", "p5_n2_measurement_audit_findings_v1.json")))
    assert "Phi_m_n_eta_SP_n_xi_N" in f["not_admissible_as_targets"] and len(f["open_decisions_for_preregistration"]) == 6

def test_p5_n2_validation_preregistration():
    """P5-N2 criteria (owner decisions D1-D6): the addendum makes a numerically valid extinction FAIL_VALIDATION/SUSTAINMENT;
    thrust scored at N1-N3 only with 5.2 / 5.6 / 5.6 mN; I_d 15 %; vacuum primary; the pinned inputs (audit values, case set,
    transport candidates, chemistry configs) match their recorded sha256; the case set equals a fresh generation; and the
    blind envelope reads its own immutable operating-point snapshot."""
    import hashlib, importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__)); B = os.path.join(root, "hallthruster_bridge")
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    add = json.load(open(os.path.join(B, "prereg", "p5_n2_run_status_rule_v1_addendum1_extinction.json")))
    assert add["amends"] == "p5_n2_run_status_rule_v1" and add["rule"]["FAIL_VALIDATION_reasons"] == ["CURRENT", "THRUST", "SUSTAINMENT"]
    c = json.load(open(os.path.join(B, "prereg", "p5_n2_validation_criteria_v1.json")))
    assert c["D1_observables"]["primary"]["thrust"] == ["N1", "N2", "N3"]
    assert c["D3_tolerances"]["thrust_mN"] == {"N1": 5.2, "N2": 5.6, "N3": 5.6}
    assert c["D4_modes"]["vacuum"]["role"].startswith("PRIMARY")
    pin = c["inputs_pinned"]
    assert h(os.path.join(B, pin["measurement_audit"]["file"])) == pin["measurement_audit"]["sha256"]
    assert h(os.path.join(B, pin["cases"]["file"])) == pin["cases"]["sha256"]
    assert h(os.path.join(B, pin["transport_candidates"]["file"])) == pin["transport_candidates"]["sha256"]
    for f, sha in pin["chemistry_configs_sha256"].items():
        assert h(os.path.join(B, "propellants", f)) == sha, f
    spec = importlib.util.spec_from_file_location("m", os.path.join(root, "scripts", "make_p5_n2_cases.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    cases = json.load(open(os.path.join(B, "cases", "p5_n2.json")))["cases"]
    assert cases == json.loads(json.dumps(m.cases())) and len(cases) == 30
    assert all(("T_tolerance_mN" in x["measured"]) == (x["point"] in ("N1", "N2", "N3")) for x in cases)
    man = json.load(open(os.path.join(B, "audit", "configs", "MANIFEST.json")))["case_files"]
    snap = os.path.join(B, "audit", "configs", "p5_n2_cases_blind_envelope_v1.json")
    assert h(snap) == man["p5_n2_cases_blind_envelope_v1.json"]["sha256"]
    assert "p5_n2_cases_blind_envelope_v1.json" in open(os.path.join(B, "checks", "blind_state_envelope.jl")).read()
    assert "pending_owner_confirmation" not in c and set(c["operational_rules"]) == {
        "O1_extinction_SUSTAINMENT", "O2_precedence", "O3_verdicts", "O4_staged_escalation", "O5_ExB_diagnostic"}
    assert c["operational_rules"]["O2_precedence"]["order"] == ["NUMERICAL_FAILURE", "OUT_OF_DOMAIN", "FAIL_VALIDATION", "PASS"]
    assert "0.05 x I_d,target" in c["operational_rules"]["O1_extinction_SUSTAINMENT"]["rule"]
    assert "N2 2.8 mN" in " ".join(c["operational_rules"]["O4_staged_escalation"]["escalate_to_other_three_primary_combinations_if_any_vacuum"])
    # every staged sensitivity and escalation config differs from its pair in exactly the intended rate files
    import tomllib
    files = lambda f: sorted(r["rate_coeff_file"] for r in tomllib.load(open(os.path.join(B, "propellants", f), "rb"))["reactions"])
    for sens, spec in c["staged_sensitivities"].items():
        d_sens = set(files(sens)) ^ set(files(spec["baseline"]))
        assert d_sens, sens
        for prim, esc in spec["escalation"].items():
            assert set(files(esc)) ^ set(files(prim)) == d_sens, esc                 # same sensitivity change on each combination
            assert set(files(esc)) ^ set(files(sens)) == set(files(prim)) ^ set(files(spec["baseline"])), esc
    assert c["staged_sensitivities"]["n2_n_n2dication.toml"]["baseline"] == "n2_n_di_lower.toml"
    lock = json.load(open(os.path.join(B, "prereg", "p5_n2_prereg_lock_v1.json")))
    for f, sha in lock["files"].items():
        assert h(os.path.join(B, f)) == sha, f

def test_p5_n2_scorer_implements_frozen_rules():
    """Synthetic records only (no campaign data): O2 precedence, O1 extinction vs breathing vs low steady current, CURRENT and
    N1-N3 THRUST tolerances with the divergence reading, N4/N5 thrust unscored, O3 member / candidate aggregation, O4 triggers."""
    import importlib.util, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("s", os.path.join(root, "scripts", "score_p5_n2_campaign.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

    def rec(point="N1", mode="vacuum", I=None, T_mN=None, samples=None, fout=0.0, retcode="success", cand="c1", chem="n2_n.toml",
            reg="L32-anode", coil="1p6kW", finite=True):
        It, Tt = m.targets(point, mode)
        I = It if I is None else I
        f = m.axial_factor(point, "A") or 1.0
        T = (Tt if T_mN is None else T_mN) / f
        return {"key": f"{cand}|{chem}|{point}-{reg}-{coil}|{mode}", "candidate": cand, "chemistry": chem, "case": f"{point}-{reg}-{coil}",
                "point": point, "registration": reg, "coil_shape": coil, "mode": mode, "retcode": retcode, "finite": finite,
                "discharge_current_A": I, "thrust_N": T * 1e-3, "Id_final10_samples_A": samples if samples is not None else [I] * 50,
                "chemistry_per_reaction": [{"extrapolated_fraction": fout}], "chemistry_unresolved_rate_files": []}
    It, Tt = m.targets("N1", "vacuum")
    assert m.run_status(rec(), "A")[0] == "PASS"
    assert m.run_status(rec(retcode="failure"), "A")[0] == "NUMERICAL_FAILURE"
    assert m.run_status(rec(finite=False), "A")[0] == "NUMERICAL_FAILURE"
    assert m.run_status(rec(fout=1e-3, samples=[0.0] * 50), "A")[0] == "OUT_OF_DOMAIN"          # collapse outside domain
    st, why, _ = m.run_status(rec(I=0.01 * It, samples=[0.001 * It] * 50), "A")
    assert st == "FAIL_VALIDATION" and "SUSTAINMENT" in why                                     # persistent collapse
    st, why, _ = m.run_status(rec(samples=[0.0] * 20 + [1.6 * It] * 30), "A")                   # deep breathing, lit
    assert "SUSTAINMENT" not in why
    st, why, _ = m.run_status(rec(I=0.5 * It, samples=[0.5 * It] * 50), "A")                    # low steady current
    assert why == ["CURRENT"]
    assert m.run_status(rec(I=1.149 * It), "A")[0] == "PASS" and m.run_status(rec(I=1.151 * It), "A")[1] == ["CURRENT"]
    assert m.run_status(rec(T_mN=Tt + 5.1), "A")[0] == "PASS" and m.run_status(rec(T_mN=Tt + 5.3), "A")[1] == ["THRUST"]
    It4, Tt4 = m.targets("N4", "vacuum")
    r4 = rec(point="N4"); r4["thrust_N"] = 10 * r4["thrust_N"]
    assert m.run_status(r4, "A")[0] == "PASS"                                                    # N4 thrust unscored
    assert m.targets("N1", "facility")[0] > It                                                   # raw > corrected current
    # aggregation: one member all PASS -> PROMOTABLE; a failing run under every member -> FAIL_VALIDATION
    good = [rec(point=p, chem=c) for c in m.MANDATORY for p in m.POINTS]
    _, mem = m.score(good)
    assert mem["vacuum"]["c1"]["candidate"] == "PROMOTABLE" and mem["vacuum"]["c1"]["members"]["L32-anode|1p6kW|A"] == "PASS"
    bad = [rec(point=p, chem=c, I=(1.5 * m.targets(p, "vacuum")[0] if p == "N2" else None)) for c in m.MANDATORY for p in m.POINTS]
    assert m.score(bad)[1]["vacuum"]["c1"]["candidate"] == "FAIL_VALIDATION"
    ood = [rec(point=p, chem=c, fout=(1e-3 if p == "N5" else 0.0)) for c in m.MANDATORY for p in m.POINTS]
    assert m.score(ood)[1]["vacuum"]["c1"]["candidate"] == "INCONCLUSIVE / NOT ELIGIBLE"
    assert m.score(good[:-1])[1]["vacuum"]["c1"]["candidate"] == "INCONCLUSIVE / NOT ELIGIBLE"      # a missing run never passes
    # O4 triggers
    base = [rec(point="N2", chem="n2_n.toml")]
    I2, T2 = m.targets("N2", "vacuum")
    assert m.escalation([rec(point="N2", chem="s", I=1.07 * I2)], base, "s") == []
    assert m.escalation([rec(point="N2", chem="s", I=1.08 * I2)], base, "s")
    onA = lambda fired: [f for f in fired if f[1].endswith("(A)")]          # fixtures set thrust through reading A's factor
    assert onA(m.escalation([rec(point="N2", chem="s", T_mN=T2 + 2.7)], base, "s")) == []
    assert onA(m.escalation([rec(point="N2", chem="s", T_mN=T2 + 2.9)], base, "s"))
    # O4 compares observables even when both runs are OUT_OF_DOMAIN (review, PR #28)
    ood_base = [rec(point="N2", chem="n2_n.toml", fout=1e-3)]
    assert m.escalation([rec(point="N2", chem="s", fout=1e-3)], ood_base, "s") == []
    assert m.escalation([rec(point="N2", chem="s", fout=1e-3, I=1.2 * I2)], ood_base, "s")
    # staged records are scored for O4 against their pre-registered baseline, not discarded
    jl = [rec(point=p, chem="n2_n_exc_johnsonlow.toml", I=(1.2 * m.targets(p, "vacuum")[0] if p == "N3" else None)) for p in m.POINTS]
    st = m.staged_escalations(good + jl)
    assert st["n2_n_exc_johnsonlow.toml"]["baseline"] == "n2_n.toml" and st["n2_n_exc_johnsonlow.toml"]["trigger_fired"]
    dic = [rec(point=p, chem="n2_n_n2dication.toml") for p in m.POINTS]
    assert m.staged_escalations(good + dic)["n2_n_n2dication.toml"]["baseline"] == "n2_n_di_lower.toml"
    assert not m.staged_escalations(good + dic)["n2_n_n2dication.toml"]["trigger_fired"]
    # O4 verdict clause on the FULL mandatory set (owner review, PR #28): members M1 = L32-anode, M2 = L38-hist
    def member(chem, reg, fail):
        return [rec(point=p, chem=chem, reg=reg, I=(1.5 * m.targets(p, "vacuum")[0] if (fail and p == "N2") else None))
                for p in m.POINTS]
    others = [c for c in m.MANDATORY if c != "n2_n.toml"]
    def full(nominal_m1_fail, nominal_m2_fail, other_m1_fail, other_m2_fail):
        out = member("n2_n.toml", "L32-anode", nominal_m1_fail) + member("n2_n.toml", "L38-hist", nominal_m2_fail)
        for c in others:
            out += member(c, "L32-anode", other_m1_fail) + member(c, "L38-hist", other_m2_fail)
        return out
    sens = lambda m1_fail, m2_fail: [dict(r, chemistry="n2_n_exc_johnsonlow.toml") for r in
                                     member("n2_n.toml", "L32-anode", m1_fail) + member("n2_n.toml", "L38-hist", m2_fail)]
    # (1) single-chemistry candidate verdict unchanged (PROMOTABLE via M1 -> via M2) but the full verdict changes (M2 fails elsewhere)
    base1 = full(False, True, False, True)
    assert m.score(base1)[1]["vacuum"]["c1"]["candidate"] == "PROMOTABLE"
    vc = m.verdict_change(sens(True, False), base1, "n2_n.toml")
    assert vc["c1"]["candidate"] == ("PROMOTABLE", "FAIL_VALIDATION")
    assert m.staged_escalations(base1 + sens(True, False))["n2_n_exc_johnsonlow.toml"]["trigger_fired"]
    # (2) converse: the single-chemistry verdict changes, but the other chemistries already falsify every member -> no change
    base2 = full(False, True, True, True)
    assert m.score(base2)[1]["vacuum"]["c1"]["candidate"] == "FAIL_VALIDATION"
    assert m.verdict_change(sens(True, True), base2, "n2_n.toml") == {}

def test_p5_n2_freeze_and_score_once(tmp_path):
    """Synthetic records only: canonical merge is shard-order independent, duplicates are refused, the dataset hash is bound in
    the manifest, the frozen scorer refuses a tampered dataset and refuses to score twice."""
    import importlib.util, json, os, gzip
    root = os.path.dirname(os.path.dirname(__file__))
    load = lambda n: (lambda spec: (spec, importlib.util.module_from_spec(spec)))(
        importlib.util.spec_from_file_location(n, os.path.join(root, "scripts", n + ".py")))
    spec, fz = load("freeze_p5_n2_dataset"); spec.loader.exec_module(fz)
    spec, sf = load("score_p5_n2_frozen"); spec.loader.exec_module(sf)
    recs = [{"key": f"c1|n2_n.toml|N{i}-L32-anode-1p6kW|vacuum", "candidate": "c1", "chemistry": "n2_n.toml",
             "case": f"N{i}-L32-anode-1p6kW", "point": f"N{i}", "registration": "L32-anode", "coil_shape": "1p6kW",
             "mode": "vacuum", "retcode": "failure", "smoke": False} for i in range(1, 6)]
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text("".join(json.dumps(r) + "\n" for r in recs[:3])); b.write_text("".join(json.dumps(r) + "\n" for r in recs[3:]))
    d1, n1 = fz.canonical([str(a), str(b)]); d2, _ = fz.canonical([str(b), str(a)])
    assert d1 == d2 and n1 == 5
    dup = tmp_path / "dup.jsonl"; dup.write_text(json.dumps(recs[0]) + "\n")
    with _pytest.raises(SystemExit):
        fz.canonical([str(a), str(dup)])
    fz._gate = lambda: type("G", (), {"audit": staticmethod(lambda mode, paths: {"PASS": True, "n_records": 5, "n_expected": 5,
                                                                                 "retcode_counts": {}, "grid": {}})})
    out = tmp_path / "val"
    perm = tmp_path / "perm.jsonl"                                                     # identity fields permuted vs keys
    rp_ = [dict(r) for r in recs]; rp_[0]["point"], rp_[1]["point"] = rp_[1]["point"], rp_[0]["point"]
    perm.write_text("".join(json.dumps(r) + "\n" for r in rp_))
    assert fz.record_identity([str(perm)]) and not fz.record_identity([str(a), str(b)])
    with _pytest.raises(SystemExit):
        fz.freeze("vacuum", [str(perm)], tag="perm", outdir=str(out))
    man = fz.freeze("vacuum", [str(a), str(b)], tag="test", outdir=str(out))
    assert man["n_records"] == 5 and len(man["sha256_canonical_jsonl"]) == 64
    with _pytest.raises(SystemExit):                                                   # never overwrite a frozen dataset
        fz.freeze("vacuum", [str(a), str(b)], tag="test", outdir=str(out))
    mp = str(out / "p5_n2_campaign_test_vacuum_raw_manifest.json")
    man_rel = json.load(open(mp)); man_rel["dataset"] = os.path.relpath(str(out / "p5_n2_campaign_test_vacuum_raw.jsonl.gz"), sf.BR)
    json.dump(man_rel, open(mp, "w"))
    p = sf.score_frozen(mp)
    assert p["input_sha256_canonical_jsonl"] == man["sha256_canonical_jsonl"] and p["input_n_records"] == 5
    assert json.load(open(os.path.join(sf.BR, p["output"])))["status_counts"]["vacuum"] == {"NUMERICAL_FAILURE": 10}
    with _pytest.raises(SystemExit):                                                   # score once
        sf.score_frozen(mp)
    # a scorer that differs from the frozen scorer is refused BEFORE it produces anything
    fake = tmp_path / "score_p5_n2_campaign.py"; fake.write_text(open(sf.SCORER).read() + "\n# modified\n")
    real_scorer, sf.SCORER = sf.SCORER, str(fake)
    try:
        with _pytest.raises(SystemExit):
            sf.score_frozen(mp, allow_existing=True)
    finally:
        sf.SCORER = real_scorer
    # an interrupted scoring attempt leaves no official artifact
    os.remove(os.path.join(sf.BR, p["output"])); os.remove(mp.replace("_raw_manifest.json", "_scores_provenance.json"))
    class Boom:
        def main(self, argv):
            open(argv[argv.index("--out") + 1], "w").write("{partial")
            raise RuntimeError("interrupted")
    real_load, sf._load_scorer = sf._load_scorer, (lambda: Boom())
    try:
        with _pytest.raises(RuntimeError):
            sf.score_frozen(mp)
    finally:
        sf._load_scorer = real_load
    assert not os.path.exists(os.path.join(sf.BR, p["output"]))
    assert not any(f.name.startswith("p5_n2_campaign_test_vacuum_scores") for f in out.iterdir())
    orphan = mp.replace("_raw_manifest.json", "_scores.json")                         # hard-interruption orphan (no provenance)
    open(orphan, "w").write("{}")
    real_link = sf.os.link
    def failing_link(src, dst):
        if dst.endswith("_scores_provenance.json"):
            raise OSError("simulated failure publishing provenance")
        return real_link(src, dst)
    sf.os.link = failing_link
    try:
        with _pytest.raises(OSError):
            sf.score_frozen(mp)
    finally:
        sf.os.link = real_link
    assert not os.path.exists(orphan)                                                  # rolled back, nothing official
    # a concurrent attempt that publishes first is never overwritten (PR #30 review): no-replace publication
    prov_path = mp.replace("_raw_manifest.json", "_scores_provenance.json")
    class Racer:
        def main(self, argv):
            real_load().main(argv)
            open(orphan, "w").write('{"other": 1}'); open(prov_path, "w").write('{"other": 1}')
    sf._load_scorer = lambda: Racer()
    try:
        with _pytest.raises(SystemExit):
            sf.score_frozen(mp)
    finally:
        sf._load_scorer = real_load
    assert open(orphan).read() == open(prov_path).read() == '{"other": 1}'
    os.remove(orphan); os.remove(prov_path)
    open(orphan, "w").write("{}")
    assert sf.score_frozen(mp)["output_sha256"]                                        # orphan removed; clean attempt succeeds
    # release manifest binds the whole chain and refuses a broken link
    spec = importlib.util.spec_from_file_location("rp", os.path.join(root, "scripts", "report_p5_n2_campaign.py"))
    rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
    scores_path = mp.replace("_raw_manifest.json", "_scores.json")
    rp.main([scores_path])
    spec = importlib.util.spec_from_file_location("rel", os.path.join(root, "scripts", "make_validation_release.py"))
    rl = importlib.util.module_from_spec(spec); spec.loader.exec_module(rl)
    r = rl.release(mp, bridge_dir=sf.BR)
    assert all(r["link_checks"].values()) and r["dataset"]["n_records"] == 5 and r["decision"]["promotable"] == []
    rel_out = str(tmp_path / "VALIDATION_RELEASE_test.json")
    real_dump = rl.json.dump
    def dying_dump(obj, fh, **kw):
        fh.write("{trunc"); raise KeyboardInterrupt
    rl.json.dump = dying_dump
    try:
        with _pytest.raises(KeyboardInterrupt):
            rl.publish(r, rel_out)
    finally:
        rl.json.dump = real_dump
    assert not os.path.exists(rel_out) and not any("VALIDATION_RELEASE_test" in f.name for f in tmp_path.iterdir())
    rl.publish(r, rel_out)
    assert json.load(open(rel_out))["link_checks"] == r["link_checks"]
    before = open(rel_out).read()
    with _pytest.raises(SystemExit):                                                   # concurrent/second publication refused
        rl.publish(dict(r, campaign="other"), rel_out)
    assert open(rel_out).read() == before and not any(".partial-" in f.name for f in tmp_path.iterdir())
    dec_path = scores_path.replace(".json", "_decision.json")
    d = json.load(open(dec_path)); d["source_scores_sha256"] = "0" * 64; json.dump(d, open(dec_path, "w"))
    with _pytest.raises(SystemExit):
        rl.release(mp, bridge_dir=sf.BR)
    for suffix in ("_decision.json", "_report.md"):
        os.remove(scores_path.replace(".json", suffix))
    gz = out / "p5_n2_campaign_test_vacuum_raw.jsonl.gz"                               # tampering is detected
    gz.write_bytes(gzip.compress(gzip.decompress(gz.read_bytes()).replace(b"failure", b"success")))
    with _pytest.raises(SystemExit):
        sf.score_frozen(mp, allow_existing=True)

def test_p5_n2_report_and_decision_are_mechanical(tmp_path):
    """Synthetic scorer output only: the decision file transcribes the vacuum O3 verdicts (facility never gates), and the report
    contains the five sections in the pre-agreed order with signed residuals."""
    import importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("s", os.path.join(root, "scripts", "score_p5_n2_campaign.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    spec = importlib.util.spec_from_file_location("r", os.path.join(root, "scripts", "report_p5_n2_campaign.py"))
    rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)

    def rec(cand, chem, p, mode="vacuum", scale=1.0):
        It, Tt = m.targets(p, mode); f = m.axial_factor(p, "A") or 1.0
        return {"key": f"{cand}|{chem}|{p}-L32-anode-1p6kW|{mode}", "candidate": cand, "chemistry": chem, "case": f"{p}-L32-anode-1p6kW",
                "point": p, "registration": "L32-anode", "coil_shape": "1p6kW", "mode": mode, "retcode": "success", "finite": True,
                "discharge_current_A": scale * It, "thrust_N": Tt / f * 1e-3, "Id_final10_samples_A": [scale * It] * 20,
                "chemistry_per_reaction": [{"extrapolated_fraction": 0.0}], "chemistry_unresolved_rate_files": []}
    recs = [rec("good", c, p) for c in m.MANDATORY for p in m.POINTS] + [rec("low", c, p, scale=0.8) for c in m.MANDATORY for p in m.POINTS] \
        + [rec("good", c, p, mode="facility", scale=0.8) for c in m.MANDATORY for p in m.POINTS]
    runs, members = m.score(recs)
    scores = {"preregistration": "x", "n_records": len(recs), "candidates": members, "runs": runs, "exb_diagnostic": {}, "staged_escalation": {}}
    d = rp.decision(scores)
    assert d["promotable"] == ["good"] and d["failed_validation"] == ["low"] and d["candidates"]["good"] == "PROMOTABLE"
    assert d["facility_verdicts_non_gating"]["good"] == "FAIL_VALIDATION"                # facility shown, never gates
    md = rp.report(scores)
    heads = [md.index(h) for h in ("## 1. Candidate verdicts", "## 2. Global layer-1", "## 3. Run status", "## 4. Signed residuals", "## 5. E×B")]
    assert heads == sorted(heads) and "-0.200" in md                                       # signed, not absolute
    import re as _re                                         # member keys contain "|": escaped, so every row has equal columns
    sec2 = md[md.index("## 2. Global layer-1"):md.index("## 3. Run status")]
    ncols = {len(_re.split(r"(?<!\\)\|", l)) for l in sec2.splitlines() if l.startswith("|")}
    assert len(ncols) == 1, ncols

def test_admission_gate_and_launch_manifests(tmp_path):
    """Admitted members need an offline-verifiable admission record (decision + provenance files, sha256, PROMOTABLE, passing
    layer-1 members); screening candidates are refused by require_admitted; the launch manifests equal a fresh build and their
    structural check works."""
    import copy, hashlib, importlib.util, json, os
    from abep_sim import hall_ensemble as he
    root = os.path.dirname(os.path.dirname(__file__))
    e = json.load(open(he.ENSEMBLE_FILE))
    bdir = tmp_path / "bridge"; (bdir / "ensemble").mkdir(parents=True); (bdir / "validation").mkdir()
    (bdir / "validation" / "s.json").write_text('{"scores": 1}')
    s_sha = hashlib.sha256((bdir / "validation" / "s.json").read_bytes()).hexdigest()
    dec = {"candidates": {"sgb-screen-01": "PROMOTABLE"}, "passing_members": {"sgb-screen-01": ["L32-anode|1p6kW|A"]},
           "source_scores_sha256": s_sha}
    (bdir / "validation" / "d.json").write_text(json.dumps(dec))
    (bdir / "validation" / "p.json").write_text(json.dumps({"output": "validation/s.json", "output_sha256": s_sha,
                                                            "input_sha256_canonical_jsonl": "m" * 64}))
    sha = lambda f: hashlib.sha256((bdir / "validation" / f).read_bytes()).hexdigest()
    (bdir / "prereg").mkdir()                          # O4: one staged sensitivity with one escalation combination
    (bdir / "prereg" / "x.json").write_text(json.dumps({"staged_sensitivities": {"sens.toml": {
        "baseline": "n2_n.toml", "escalation": {"n2_n_di_lower.toml": "sens_di_lower.toml"}}}}))
    def o4_scored(name, chem, fired, mand="m" * 64):
        (bdir / "validation" / f"{name}_s.json").write_text(json.dumps({"staged_escalation": {chem: {"trigger_fired": fired}}}))
        (bdir / "validation" / f"{name}_p.json").write_text(json.dumps({
            "mode": "vacuum", "input_mandatory_sha256": mand, "mandatory_scores_sha256": s_sha,
            "output": f"validation/{name}_s.json", "output_sha256": sha(f"{name}_s.json")}))
        return {"scores_provenance_file": f"validation/{name}_p.json", "scores_provenance_sha256": sha(f"{name}_p.json")}
    def o4_file(name, fired=False, escalations=None, cleared=("sgb-screen-01",), recorded=None, first=None, disp="owner text"):
        d = {"schema": "o4_dispositions_v1", "campaign_id": "p5_n2_campaign_v1", "mandatory_decision_sha256": sha("d.json"),
             "sensitivities": {"sens.toml": {"baseline": "n2_n.toml", "first_stage": first or o4_scored(name + "_st", "sens.toml", fired),
                                             "trigger_fired": fired if recorded is None else recorded,
                                             "escalations": escalations or {}, "disposition": disp}},
             "cleared_for_admission": list(cleared), "decided_by": "owner", "decided_utc": "t"}
        (bdir / "validation" / f"{name}.json").write_text(json.dumps(d))
        return {"o4_dispositions_file": f"validation/{name}.json", "o4_dispositions_sha256": sha(f"{name}.json")}
    cand = copy.deepcopy(e["screening_candidates"][0])
    adm = {"promoted_from_screening_id": "sgb-screen-01", "campaign_id": "p5_n2_campaign_v1", "preregistration": "prereg/x.json",
           "decision_file": "validation/d.json", "decision_sha256": sha("d.json"), "scores_provenance_file": "validation/p.json",
           "scores_provenance_sha256": sha("p.json"), "passing_layer1_members": ["L32-anode|1p6kW|A"], "admitted_utc": "t", "decided_by": "owner",
           **o4_file("o4ok")}
    def write(member, drop_from_screening=True):
        ee = copy.deepcopy(e); ee["members"] = [member]
        if drop_from_screening:
            ee["screening_candidates"] = [c for c in ee["screening_candidates"] if c["ensemble_member_id"] != member["ensemble_member_id"]]
        pth = bdir / "ensemble" / "transport_ensemble_v0.json"; pth.write_text(json.dumps(ee)); return str(pth)
    with _pytest.raises(ValueError):                                        # no admission record
        he.load_ensemble(write(copy.deepcopy(cand)))
    ok = he.load_ensemble(write(dict(copy.deepcopy(cand), admission=adm)))
    he.require_admitted("sgb-screen-01", ok)
    with _pytest.raises(ValueError):                                        # still also listed as screening
        he.load_ensemble(write(dict(copy.deepcopy(cand), admission=adm), drop_from_screening=False))
    with _pytest.raises(ValueError):                                        # tampered decision
        he.load_ensemble(write(dict(copy.deepcopy(cand), admission=dict(adm, decision_sha256="0" * 64))))
    (bdir / "validation" / "p3.json").write_text(json.dumps({"output": "validation/missing.json", "output_sha256": s_sha}))
    with _pytest.raises(ValueError):                                        # scores file named by provenance is missing
        he.load_ensemble(write(dict(copy.deepcopy(cand), admission=dict(adm, scores_provenance_file="validation/p3.json",
                                                                           scores_provenance_sha256=sha("p3.json")))))
    (bdir / "validation" / "p2.json").write_text(json.dumps({"output_sha256": "b" * 64}))   # provenance of a different scores file
    with _pytest.raises(ValueError):
        he.load_ensemble(write(dict(copy.deepcopy(cand), admission=dict(adm, scores_provenance_file="validation/p2.json",
                                                                           scores_provenance_sha256=sha("p2.json")))))
    with _pytest.raises(ValueError):                                        # unsupported passing member
        he.load_ensemble(write(dict(copy.deepcopy(cand), admission=dict(adm, passing_layer1_members=["L38-hist|3p0kW|B"]))))
    # owner follow-up on PR #29: PROMOTABLE alone never admits; the O4 stage must be scored and dispositioned
    no_o4 = {k: v for k, v in adm.items() if not k.startswith("o4_")}
    refused = {"no O4 record": no_o4,
               "not cleared": dict(adm, **o4_file("o4a", cleared=())),
               "recorded trigger contradicts the scored one": dict(adm, **o4_file("o4b", fired=True, recorded=False)),
               "trigger fired, escalation not scored": dict(adm, **o4_file("o4c", fired=True)),
               "no disposition text": dict(adm, **o4_file("o4d", disp=" ")),
               "scored against another mandatory dataset": dict(adm, **o4_file("o4e", first=o4_scored("o4e_st", "sens.toml", False, "x" * 64))),
               "tampered O4 record": dict(adm, o4_dispositions_sha256="0" * 64)}
    for why, a in refused.items():
        with _pytest.raises(ValueError):
            he.load_ensemble(write(dict(copy.deepcopy(cand), admission=a)))
    esc = {"sens_di_lower.toml": o4_scored("o4f_esc", "sens_di_lower.toml", False)}
    ok2 = he.load_ensemble(write(dict(copy.deepcopy(cand), admission=dict(adm, **o4_file("o4f", fired=True, escalations=esc)))))
    he.require_admitted("sgb-screen-01", ok2)                              # fired + every escalation scored + dispositioned
    with _pytest.raises(ValueError):                                        # the real ensemble: screening refused
        he.require_admitted("sgb-screen-01")
    spec = importlib.util.spec_from_file_location("mm", os.path.join(root, "scripts", "make_p5_n2_launch_manifests.py"))
    mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)
    built = {m["name"]: m for m in mm.build()}
    assert len(built) == 19 and built["facility_mandatory"]["n_runs"] == 1080
    assert built["staged_n2_n_n2dication"]["baseline"] == "n2_n_di_lower.toml"
    for name, m in built.items():
        assert json.load(open(os.path.join(mm.OUT, name + ".json"))) == json.loads(json.dumps(m)), name
    m = built["staged_n2_n_rot_off"]
    lock = m["prereg_lock_sha256"]; commit = "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5"
    f = tmp_path / "s.jsonl"
    f.write_text("".join(json.dumps({"key": k, "mode": "vacuum", "smoke": False, "prereg_lock_sha256": lock,
                                     "hallthruster_commit": commit, "retcode": "success"}) + "\n" for k in m["expected_keys"]))
    assert mm.check(m, [str(f)])["PASS"]
    assert not mm.check(built["staged_n2_n_ndd_hmslow"], [str(f)])["PASS"]

def test_staged_o4_freeze_and_score_once(tmp_path):
    """O4 datasets (scripts/score_p5_n2_staged.py): frozen against the pinned launch manifest, scored once with the frozen
    scorer on mandatory + staged records; the mandatory scores must be reproduced exactly. A copy of the baseline relabelled as
    the sensitivity fires no trigger; a +10 % current perturbation fires it; re-scoring and re-freezing are refused."""
    import gzip, importlib.util, json, os
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("st", os.path.join(root, "scripts", "score_p5_n2_staged.py"))
    st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
    raw = gzip.decompress(open(os.path.join(root, "hallthruster_bridge", "validation", "p5_n2_campaign_v1_vacuum_raw.jsonl.gz"), "rb").read())
    def staged(sens, scale):
        f = tmp_path / f"{sens}.jsonl"
        with open(f, "w") as fh:
            for line in raw.decode().splitlines():
                r = json.loads(line)
                if r["chemistry"] == "n2_n.toml":
                    r["chemistry"], r["key"] = sens + ".toml", r["key"].replace("|n2_n.toml|", f"|{sens}.toml|")
                    if isinstance(r.get("discharge_current_A"), (int, float)):
                        r["discharge_current_A"] *= scale
                    fh.write(json.dumps(r) + "\n")
        man = os.path.join(root, "hallthruster_bridge", "campaign", "manifests", f"staged_{sens}.json")
        st.freeze_staged(man, [str(f)], tag="t", outdir=str(tmp_path))
        return man, str(f), str(tmp_path / f"p5_n2_campaign_t_staged_{sens}_raw_manifest.json")
    man, f, fm = staged("n2_n_rot_off", 1.0)
    p = st.score_staged(fm)
    assert p["mandatory_reproduced"] and p["o4_trigger_fired"] == {"n2_n_rot_off.toml": False}
    with _pytest.raises(SystemExit):
        st.score_staged(fm)                                                # score once
    with _pytest.raises(SystemExit):
        st.freeze_staged(man, [f], tag="t", outdir=str(tmp_path))          # no overwrite
    with _pytest.raises(SystemExit):                                       # wrong launch manifest for these records
        st.freeze_staged(man.replace("rot_off", "ndd_hmslow"), [f], tag="u", outdir=str(tmp_path))
    assert st.score_staged(staged("n2_n_ndd_hmslow", 1.10)[2])["o4_trigger_fired"] == {"n2_n_ndd_hmslow.toml": True}

def test_rate_table_tail_policy_is_explicit():
    """Beyond the last tabulated energy, "hold" keeps the last value and "zero" drops it; anything else is refused."""
    from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity
    import numpy as np
    E = np.array([12.0, 200.0]); s = np.array([1e-20, 1e-20])
    assert maxwellian_rate(E, s, 100.0, "hold") > maxwellian_rate(E, s, 100.0, "zero")
    assert abs(maxwellian_rate(E, s, 3.0, "hold") / maxwellian_rate(E, s, 3.0, "zero") - 1) < 1e-9
    assert tail_sensitivity(E, s, [4.5])[0][1] < 1e-9
    with _pytest.raises(ValueError):
        maxwellian_rate(E, s, 10.0, "extrapolate")


def test_n2_dissociation_rate_table_reproduces_jpcrd_table9():
    """dissociation_N2.dat (Song et al. JPCRD 2023 Table 9 = Cosby 1993, scripts/build_n2_dissociation_table.py):
    header = N(2D)+N(4S) energy loss, zero below the 12 eV first point, and each row equals a fresh integration of the
    transcribed table with the declared hold tail. The tail share is < 1 % up to 45 eV mean energy."""
    import importlib.util, os, numpy as np
    from abep_sim.rate_tables import maxwellian_rate, tail_sensitivity
    root = os.path.dirname(os.path.dirname(__file__))
    spec = importlib.util.spec_from_file_location("b", os.path.join(root, "scripts", "build_n2_dissociation_table.py"))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    d = os.path.join(root, "hallthruster_bridge", "propellants")
    lines = open(os.path.join(d, "dissociation_N2.dat")).read().splitlines()
    assert lines[0] == "Dissociation energy loss (eV): 12.14"
    a = np.loadtxt(os.path.join(d, "dissociation_N2.dat"), skiprows=2)
    assert a[0, 1] == 0.0 and (a[:, 1] >= 0).all() and a[-1, 0] >= 255
    E = np.array([e for e, _ in b.TABLE9]); sig = np.array([x for _, x in b.TABLE9]) * 1e-20
    assert len(E) == 16 and E[0] == 12 and E[-1] == 200 and abs(sig.max() - 1.23e-20) < 1e-30
    for eps in (15.0, 30.0, 60.0, 150.0):
        row = a[a[:, 0] == eps][0, 1]
        assert abs(row / maxwellian_rate(E, sig, eps / 1.5, b.TAIL) - 1) < 1e-5
    assert all(dd < 0.01 for eps, dd in tail_sensitivity(E, sig, [15, 30, 45]))
    src = open(os.path.join(d, "dissociation_N2.dat.source")).read()
    assert "Table 9" in src and "Cosby" in src and "held" in src


def test_chemistry_extrapolation_makes_a_map_point_untrustworthy(tmp_path):
    """A node whose chemistry-active region exceeded a rate table's documented validity domain (chemistry_trustworthy =
    0) makes every query touching it untrustworthy, even if converged and sustained."""
    import json, numpy as np
    from abep_sim.hall_map import HallMap, REQUIRED_FIELDS, REQUIRED_META, pinned_commit
    axes = {"Vd": [250.0, 300.0], "mdot_kgps": [1e-6, 2e-6]}
    def make(ch):
        f = {k: (np.ones((2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
        f["converged"] = [[1, 1], [1, 1]]; f["sustained"] = [[1, 1], [1, 1]]; f["chemistry_trustworthy"] = ch
        meta = {k: "synthetic" for k in REQUIRED_META}
        meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"")
        p = tmp_path / f"c{ch}.json"; p.write_text(json.dumps({"meta": meta, "axes": axes, "fields": f}))
        return HallMap(str(p), ensemble=_synthetic_ensemble())(Vd=275.0, mdot_kgps=1.5e-6)
    assert make([[1, 1], [1, 1]])["trustworthy"] is True
    assert make([[1, 1], [1, 0]])["trustworthy"] is False


def test_every_committed_rate_table_has_a_validity_domain():
    """propellants/rate_validity.toml must cover every rate table present (the driver errors on a missing entry). A
    'verified' entry carries a limit within HallThruster's 0-255 eV grid and no 'verify' caveat; an 'unresolved' entry
    carries no limit, so it can never certify chemistry_trustworthy. The shipped N2 tables stay unresolved until audited."""
    import os, glob, tomllib
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "propellants")
    val = tomllib.load(open(os.path.join(d, "rate_validity.toml"), "rb"))
    for f in glob.glob(os.path.join(d, "*.dat")):
        e = val[os.path.basename(f)]
        assert e["status"] in ("verified", "unresolved") and e["basis"]
        if e["status"] == "verified":
            assert 0 < e["max_mean_energy_eV"] <= 255 and "verify" not in e["basis"].lower()
        else:
            assert "max_mean_energy_eV" not in e
    assert val["dissociation_N2.dat"]["max_mean_energy_eV"] == 45.0
    assert val["ionization_N.dat"]["max_mean_energy_eV"] == 255.0
    assert {f for f, e in val.items() if e["status"] == "unresolved"} == {"ionization_N2_N2+.dat", "elastic_N2.dat"}
    assert val["ionization_N2_song2023.dat"]["max_mean_energy_eV"] == 255.0
    assert val["elastic_N2_song2023.dat"]["max_mean_energy_eV"] == 255.0


def test_bridge_and_0d_chemistry_are_not_unified():
    """HallThruster.jl tables in hallthruster_bridge/propellants/ are NOT read by the 0-D plasma_chem model. If this
    fails, the databases were unified: that is a model change (goldens, HISTORY), so update this test deliberately."""
    from abep_sim.plasma_chem import CHEM_PROVENANCE, RATE_TABLES
    assert set(RATE_TABLES) == {("N2", "iz")}
    assert all("propellants" not in v for v in CHEM_PROVENANCE.values())


def test_wall_life_trust_is_separate_from_performance_trust(tmp_path):
    """map_ready/trustworthy never imply erosion-grade wall flux: that needs ion_wall_losses=true in the map meta AND
    wall_life_trustworthy on every surrounding node."""
    import json, numpy as np
    from abep_sim.hall_map import HallMap, REQUIRED_FIELDS, REQUIRED_META, pinned_commit
    axes = {"Vd": [250.0, 300.0], "mdot_kgps": [1e-6, 2e-6]}
    def make(ion_wall_losses, wl):
        f = {k: (np.ones((2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
        f["converged"] = [[1, 1], [1, 1]]; f["sustained"] = [[1, 1], [1, 1]]; f["wall_life_trustworthy"] = wl
        f["chemistry_trustworthy"] = [[1, 1], [1, 1]]
        meta = {k: "synthetic" for k in REQUIRED_META}
        meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"", ion_wall_losses=ion_wall_losses)
        p = tmp_path / f"m{ion_wall_losses}{wl}.json"; p.write_text(json.dumps({"meta": meta, "axes": axes, "fields": f}))
        return HallMap(str(p), ensemble=_synthetic_ensemble())(Vd=275.0, mdot_kgps=1.5e-6)
    assert make(False, [[1, 1], [1, 1]])["trustworthy"] is True
    assert make(False, [[1, 1], [1, 1]])["wall_life_trustworthy"] is False
    assert make(True, [[1, 1], [1, 0]])["wall_life_trustworthy"] is False
    assert make(True, [[1, 1], [1, 1]])["wall_life_trustworthy"] is True


def _rescore_module():
    import importlib.util, os
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "rescore_p5_axial_thrust.py")
    spec = importlib.util.spec_from_file_location("rescore_p5_axial_thrust", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def _write_runs(path, rows):
    import csv
    fields = ["hypothesis", "combo", "point", "retcode", "Id_err_rel", "T_mN", "T_target_mN", "Id_rms_rel"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def test_rescore_loo_holdout_failure_is_a_blind_failure(tmp_path):
    """A set that fits the calibration points best must be selected even if its held-out run failed, and that round must
    be recorded as a failed blind prediction (dropping failed runs before selection leaks the holdout outcome)."""
    m = _rescore_module()
    good = dict(retcode="success", T_mN="100", T_target_mN="100", Id_rms_rel="0.1")
    failed = dict(retcode="failure", T_mN="", T_target_mN="", Id_rms_rel="", Id_err_rel="")
    rows = []
    for p in ("Xe1", "Xe2", "Xe3"):          # 'best' fits every calibration point exactly but its Xe3 run failed
        best = dict(failed) if p == "Xe3" else dict(good, Id_err_rel="0.0")
        rows.append(dict(best, hypothesis="H", combo="a=1/16_b=0.8_c=1L_w=0.1L", point=p))
        rows.append(dict(good, hypothesis="H", combo="a=1/32_b=0.8_c=1L_w=0.1L", point=p, Id_err_rel="0.05"))
    f = tmp_path / "runs.csv"; _write_runs(f, rows)
    sc = m.score(m.load(str(f)), {p: 1.0 for p in m.P}, {p: 0.0 for p in m.P})
    r = {x["holdout"]: x for x in m.loo(sc, "sgb", "H", quiet_only=False)}
    assert r["Xe3"]["combo"] == "a=1/16_b=0.8_c=1L_w=0.1L"      # selected on calibration points only
    assert r["Xe3"]["hold_failed"] is True and r["Xe3"]["pass"] is False
    assert r["Xe1"]["combo"] == "a=1/32_b=0.8_c=1L_w=0.1L"      # calibration includes the failed Xe3 -> ineligible


def test_rescore_same_combo_requires_actual_selections():
    """same_combo is False when no round selected anything ({None} has one element but is not 'the same set')."""
    m = _rescore_module()
    assert m.same_combo([{"combo": None}] * 3) is False
    assert m.same_combo([{"combo": "x"}, {"combo": None}, {"combo": "x"}]) is False
    assert m.same_combo([{"combo": "x"}] * 3) is True


def test_transport_ensemble_two_layer_structure(tmp_path):
    """Layer 1 (P5 calibration nuisance) never becomes a transport parameter or a map axis; the credible set stays
    unweighted; while admission is pending, no Hall map can be loaded."""
    import copy, json, numpy as np, pytest
    from abep_sim.hall_ensemble import load_ensemble
    from abep_sim.hall_map import HallMap, REQUIRED_FIELDS, REQUIRED_META, pinned_commit
    real = load_ensemble()
    assert real["weighting"] == "unweighted" and set(real["calibration_nuisance"]) >= {
        "p5_registration", "p5_coil_shape", "beam_efficiency_reading"}
    assert real["members"] == []                                             # credible set is empty (2026-09-26)
    from abep_sim.hall_ensemble import screening_ids
    assert len(screening_ids(real)) == 9 and all(
        c["transport_parameters"]["anom_scale"] <= 1 / 16 for c in real["screening_candidates"])
    axes = {"Vd": [250.0, 300.0], "mdot_kgps": [1e-6, 2e-6]}
    f = {k: (np.ones((2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
    f["converged"] = [[1, 1], [1, 1]]; f["sustained"] = [[1, 1], [1, 1]]
    meta = {k: "synthetic" for k in REQUIRED_META}
    meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"")
    p = tmp_path / "m.json"; p.write_text(json.dumps({"meta": meta, "axes": axes, "fields": f}))
    with pytest.raises(ValueError, match="not an admitted"):
        HallMap(str(p))                                                     # real ensemble: nothing admitted yet
    HallMap(str(p), ensemble=_synthetic_ensemble())
    bad_axes = dict(axes, p5_registration=[0, 1])
    f2 = {k: (np.ones((2, 2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
    p2 = tmp_path / "m2.json"; p2.write_text(json.dumps({"meta": meta, "axes": bad_axes, "fields": f2}))
    with pytest.raises(ValueError, match="calibration-nuisance"):
        HallMap(str(p2), ensemble=_synthetic_ensemble())
    leak = copy.deepcopy(_synthetic_ensemble()); leak["members"][0]["transport_parameters"]["p5_coil_shape"] = "1p6kW"
    pe = tmp_path / "e.json"; pe.write_text(json.dumps(leak))
    with pytest.raises(ValueError, match="calibration nuisance"):
        load_ensemble(str(pe))
    weighted = copy.deepcopy(_synthetic_ensemble()); weighted["weighting"] = "bayesian"
    pw = tmp_path / "w.json"; pw.write_text(json.dumps(weighted))
    with pytest.raises(ValueError, match="unweighted"):
        load_ensemble(str(pw))


def test_screening_candidates_never_produce_hall_maps(tmp_path):
    """A screening candidate's id is not an admitted member: HallMap must reject a map that names it."""
    import json, numpy as np, pytest
    from abep_sim.hall_ensemble import load_ensemble
    from abep_sim.hall_map import HallMap, REQUIRED_FIELDS, REQUIRED_META, pinned_commit
    real = load_ensemble()
    sid = real["screening_candidates"][0]["ensemble_member_id"]
    f = {k: (np.ones((2, 2)) * 0.02).tolist() for k in REQUIRED_FIELDS}
    meta = {k: "synthetic" for k in REQUIRED_META}
    meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"", ensemble_member_id=sid)
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"meta": meta, "axes": {"Vd": [250.0, 300.0], "mdot_kgps": [1e-6, 2e-6]}, "fields": f}))
    with pytest.raises(ValueError, match="not an admitted"):
        HallMap(str(p))
