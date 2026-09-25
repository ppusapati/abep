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
    m = HallMap(str(p))                                              # SYNTHETIC map: tests the loader only
    assert m(Vd=260.0, mdot_kgps=1.2e-6)["trustworthy"] is False    # touches the unconverged node
    q = m(Vd=255.0, mdot_kgps=1.1e-6)
    assert q["wall_life_trustworthy"] is False                       # meta ion_wall_losses is the string "synthetic", not True
    with pytest.raises(ValueError):
        m(Vd=350.0, mdot_kgps=1.2e-6)                                # no extrapolation
    bad = dict(good); bad["meta"] = dict(meta, pinned="commit = \"deadbeef\"")
    p2 = tmp_path / "b.json"; p2.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        HallMap(str(p2))


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
        meta = {k: "synthetic" for k in REQUIRED_META}
        meta.update(schema="hall_map_schema_v1", pinned=f"commit = \"{pinned_commit()}\"", ion_wall_losses=ion_wall_losses)
        p = tmp_path / f"m{ion_wall_losses}{wl}.json"; p.write_text(json.dumps({"meta": meta, "axes": axes, "fields": f}))
        return HallMap(str(p))(Vd=275.0, mdot_kgps=1.5e-6)
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
