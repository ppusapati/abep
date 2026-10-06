//! Analytic limiting cases LC-01..LC-11 (prereg `analytic_limiting_cases`), with the preregistered criteria.
//! Every case is SYNTHETIC_TEST_ONLY; its numbers verify the implementation, never the hardware.

mod common;

use abep_icp::constants::{AMU, E_CHARGE, K_B, M_E, TOL_ANALYTIC};
use abep_icp::coupling;
use abep_icp::physics;
use abep_icp::testkit::*;
use abep_icp::IcpStatus;
use common::{model, rel, val};
use std::f64::consts::PI;

/// Sum of h_j A_j of the all-floating tube.
fn sum_ha() -> f64 {
    H_EDGE * (2.0 * PI * R_M * L_M + 2.0 * PI * R_M * R_M)
}

/// Independent bisection root of n_g k_iz(T) V = u_B(T) sum h A (LC-01), written without the crate's kernels.
fn independent_root() -> f64 {
    let n_g = 1.0 / (K_B * 300.0);
    let v = PI * R_M * R_M * L_M;
    let f = |t: f64| n_g * 1e-13 * (-E_IZ_X_EV / t).exp() * v - (E_CHARGE * t / (40.0 * AMU)).sqrt() * sum_ha();
    let (mut lo, mut hi) = (1.0f64, 20.0f64);
    assert!(f(lo) < 0.0 && f(hi) > 0.0);
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        if f(mid) < 0.0 {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}

#[test]
fn lc01_t_e_set_by_particle_balance_independent_of_power() {
    let m = model();
    let p1 = 7.0;
    let ts: Vec<f64> = [p1, 10.0 * p1, 100.0 * p1]
        .iter()
        .map(|p| {
            let r = m.evaluate(&floating_case(*p));
            assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
            assert!(r.flags.contains("SYNTHETIC_TEST_ONLY"));
            val(r.scalar("T_e_eV"))
        })
        .collect();
    let t_ind = independent_root();
    for t in &ts {
        assert!(rel(*t, ts[0]) <= TOL_ANALYTIC, "T_e differs across powers: {ts:?}");
        assert!(rel(*t, t_ind) <= TOL_ANALYTIC, "T_e {t} vs independent root {t_ind}");
    }
}

#[test]
fn lc02_n_e_linear_in_absorbed_power_floating_wall_energy_per_pair() {
    let m = model();
    let p1 = 7.0;
    let mut ratios = Vec::new();
    for p in [p1, 10.0 * p1, 100.0 * p1] {
        let r = m.evaluate(&floating_case(p));
        let t = val(r.scalar("T_e_eV"));
        let ne = val(r.scalar("n_e_m3"));
        let u_b = (E_CHARGE * t / (40.0 * AMU)).sqrt();
        let v_s = 0.5 * t * ((40.0 * AMU) / (2.0 * PI * M_E)).ln();
        let expected = 1.0 / (E_CHARGE * u_b * sum_ha() * (E_IZ_X_EV + 2.0 * t + 0.5 * t + v_s));
        assert!(rel(ne / p, expected) <= TOL_ANALYTIC, "n_e/P_abs {} vs {expected}", ne / p);
        ratios.push(ne / p);
    }
    assert!(rel(ratios[0], ratios[2]) <= TOL_ANALYTIC);
}

#[test]
fn lc03_zero_absorbed_power_is_not_sustained_with_exact_zeros() {
    let m = model();
    let r = m.evaluate(&capoff_case(0.0, 0.0, 30.0));
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    assert_eq!(r.plasma_state.value.as_deref(), Some("NOT_SUSTAINED"));
    assert_eq!(r.scalar("n_e_m3").value, Some(0.0));
    assert_eq!(r.scalar("I_e_cap_A").value, Some(0.0));
    assert_eq!(r.scalar("I_production_A").value, Some(0.0));
    let a = &r.if_icp_thermal_v1.assignments[0];
    for k in [
        "P_icp_abs_W",
        "Q_icp_plasma_wall_W",
        "Q_icp_extraction_W",
        "Q_icp_radiation_W",
        "Q_icp_outflow_upstream_W",
        "Q_icp_outflow_downstream_W",
        "Q_icp_bias_collector_W",
        "Q_icp_bias_export_W",
        "P_icp_collector_bias_W",
    ] {
        assert_eq!(a.keys[k].value, Some(0.0), "{k}");
    }
    // CM-CAL / CM-PRED on the n_e = 0 branch (R_p = 0): the forward power closes into reflection and circuit losses.
    let (p_fwd, p_refl, q_line, q_match, r_ant) = (200.0, 12.5, 3.25, 4.75, 0.36);
    let p_del = p_fwd - p_refl - q_line - q_match;
    let (p_abs, q_coil) = coupling::trivial_branch(p_del, r_ant);
    assert_eq!(p_abs, 0.0);
    assert_eq!(p_refl + q_line + q_match + q_coil, p_fwd);
    // CM-PRED: the trivial branch cannot be listed by an evaluable CM-PRED model in v1 (VER-03 gate, LC-11).
    let mut c = capoff_case(0.0, 0.0, 30.0);
    c.coupling_mode = abep_icp::case::CouplingMode::Predictive;
    assert_eq!(m.evaluate(&c).status, IcpStatus::NotEvaluated);
}

#[test]
fn lc04_coupling_efficiency_tends_to_one_as_antenna_resistance_vanishes() {
    let r_p = 0.04;
    for ratio in [1.0, 1e-3, 1e-6] {
        let eta = coupling::coupling_efficiency(r_p, ratio * r_p);
        assert!(rel(eta, 1.0 / (1.0 + ratio)) <= 1e-12);
    }
    assert_eq!(coupling::coupling_efficiency(r_p, 0.0), 1.0);
    let (_, p_abs, q_coil) = coupling::antenna_split(150.0, r_p, 0.0);
    assert_eq!(q_coil, 0.0);
    assert_eq!(p_abs, 150.0);
}

#[test]
fn lc05_i_e_cap_bounded_by_the_electron_thermal_flux() {
    let m = model();
    // Saturation case: A_ic >> A_ec, V_ec above phi_p.
    let r = m.evaluate(&capoff_case(50.0, 0.0, 30.0));
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    let cap = val(r.scalar("I_e_cap_A"));
    let lim = val(r.scalar("I_e_thermal_limit_A"));
    let phi = val(r.scalar("phi_p_V"));
    assert!(phi < 30.0, "V_ec must lie above phi_p = {phi}");
    assert!(rel(cap, lim) <= TOL_ANALYTIC, "saturation equality: {cap} vs {lim}");
    assert_eq!(r.equilibria[0].electron_saturated_surfaces, vec!["ec".to_string()]);
    assert!(r.verify_items_on_path.contains("VER-06"));
    // The inequality in every case of the suite (retarding and saturated electron sinks).
    for (v_ic, v_ec) in [(0.0, 30.0), (0.0, 5.0), (-5.0, 10.0), (-10.0, 0.0), (0.0, 60.0)] {
        let r = m.evaluate(&capoff_case(50.0, v_ic, v_ec));
        assert_eq!(r.status, IcpStatus::Converged, "({v_ic}, {v_ec}): {:#?}", r.reasons);
        let cap = val(r.scalar("I_e_cap_A"));
        assert!(cap <= val(r.scalar("I_e_thermal_limit_A")) * (1.0 + 1e-12), "({v_ic}, {v_ec})");
    }
}

#[test]
fn lc06_i_e_cap_bounded_by_ion_collection_and_production() {
    let m = model();
    for (v_ic, v_ec) in [(0.0, 30.0), (0.0, 5.0), (-5.0, 10.0), (-10.0, 0.0), (0.0, 60.0)] {
        let r = m.evaluate(&capoff_case(50.0, v_ic, v_ec));
        let cap = val(r.scalar("I_e_cap_A"));
        assert!(cap <= val(r.scalar("I_ion_collection_limit_A")) * (1.0 + 1e-12), "({v_ic}, {v_ec})");
        assert!(cap <= val(r.scalar("I_production_A")) * (1.0 + 1e-12), "({v_ic}, {v_ec})");
    }
    // All surfaces floating, no electron collector: exactly zero.
    let r = m.evaluate(&floating_case(50.0));
    assert_eq!(r.status, IcpStatus::Converged);
    assert_eq!(r.scalar("I_e_cap_A").value, Some(0.0));
}

#[test]
fn lc07_floating_sheath_single_species() {
    let m = model();
    let r = m.evaluate(&floating_case(20.0));
    let t = val(r.scalar("T_e_eV"));
    let vs = val(r.scalar("V_s_float_V"));
    let expected = 0.5 * t * ((40.0 * AMU) / (2.0 * PI * M_E)).ln();
    assert!(rel(vs, expected) <= 1e-12, "{vs} vs {expected}");
    assert!(rel(physics::floating_sheath_single_species(t, 40.0 * AMU), expected) <= 1e-12);
    assert_eq!(((vs / t) * 10.0).round() / 10.0, 4.7, "V_s / T_e for argon");
}

#[test]
fn lc08_lieberman_worked_example() {
    let u_b = physics::bohm_speed(3.5, 1, 40.0 * AMU);
    assert_eq!((u_b / 100.0).round() * 100.0, 2900.0);
    let h_r = physics::h_radial_lieberman(0.15, 0.03);
    let h_l = physics::h_axial_lieberman(0.3, 0.03);
    assert!(rel(h_r, 0.8 / 3.0) <= 1e-12);
    assert!(rel(h_l, 0.86 / 8f64.sqrt()) <= 1e-12);
    assert_eq!((h_r * 10.0).round() / 10.0, 0.3);
    assert_eq!((h_l * 10.0).round() / 10.0, 0.3);
    assert_eq!(physics::h_radial_lieberman(0.15, f64::INFINITY), 0.4);
    assert!(rel(physics::h_radial_lieberman(0.15, 1e30), 0.4) <= 1e-12);
}

#[test]
fn lc09_free_molecular_effusion() {
    let m = model();
    let mdot = 1e-7;
    let r = m.evaluate(&flow_case(0.0, mdot, 1.0));
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    let n = val(&r.map("n_g_m3")["X"]);
    let gamma_in = mdot / M_X_KG;
    let a = 0.5 * PI * R_M * R_M;
    let vbar = (8.0 * K_B * 300.0 / (PI * M_X_KG)).sqrt();
    assert!(rel(n, gamma_in / (0.25 * vbar * a)) <= 1e-12);
    // Chiggiato 2014 Table 4 / Table 8 with the registered N2 mass (n2_n.toml, 28.0134 u).
    let n2 = &m.n2_set.species[m.n2_set.species_index("N2").unwrap()];
    let vbar_n2 = physics::neutral_mean_speed(293.0, n2.mass_kg);
    assert!(rel(vbar_n2, 470.0) <= 2e-3, "{vbar_n2}");
    assert!(rel(0.25 * vbar_n2, 117.5) <= 2e-3);
}

#[test]
fn lc10_partition_closure_with_a_biased_electrode() {
    let m = model();
    for (v_ic, v_ec) in [(0.0, 30.0), (-5.0, 30.0), (-5.0, 10.0)] {
        let r = m.evaluate(&capoff_case(50.0, v_ic, v_ec));
        assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
        let a = &r.if_icp_thermal_v1.assignments[0];
        for c in &a.closures {
            if c.id.starts_with("CC-05") {
                assert_eq!(c.status, IcpStatus::Converged, "{c:?}");
            }
        }
        // P_collector_bias = -sum I_j V_j, computed here from the surface currents and registered potentials.
        let i = r.map("I_surface_A");
        let p_bias = -(val(&i["ic"]) * v_ic + val(&i["ec"]) * v_ec);
        let q_sum = val(&a.keys["Q_icp_bias_collector_W"]) + val(&a.keys["Q_icp_bias_export_W"]);
        assert!((p_bias - q_sum).abs() <= 1e-10 * (val(&a.keys["P_icp_abs_W"]) + p_bias.abs()));
        let p_abs = val(&a.keys["P_icp_abs_W"]);
        let part: f64 = [
            "Q_icp_plasma_wall_W",
            "Q_icp_extraction_W",
            "Q_icp_radiation_W",
            "Q_icp_outflow_upstream_W",
            "Q_icp_outflow_downstream_W",
        ]
        .iter()
        .map(|k| val(&a.keys[*k]))
        .sum();
        assert!((p_abs - part).abs() <= 1e-10 * (p_abs + p_bias.abs()));
        // Per surface Q_j = L_j + C_j equals the kinetic energy deposited, computed independently.
        let t = val(r.scalar("T_e_eV"));
        let phi = val(r.scalar("phi_p_V"));
        let geo = &abep_icp::testkit::capoff_surfaces();
        for s in geo {
            let st = &r.surface_terms[&s.id];
            let vj = val(&st.potential_v);
            let (ge, gz) = (val(&st.gamma_e_m2_s), val(&st.gamma_z_m2_s));
            let q_kin =
                E_CHARGE * s.area_m2 * (ge * (2.0 * t + (vj - phi).max(0.0)) + gz * (0.5 * t + (phi - vj).max(0.0)));
            let lc = val(&st.l_w) + val(&st.c_w);
            assert!(rel(lc, q_kin) <= 1e-12, "{}: {lc} vs {q_kin}", s.id);
        }
    }
    // Every surface floating: C_j = 0 exactly and Q_j = L_j.
    let r = m.evaluate(&floating_case(50.0));
    for st in r.surface_terms.values() {
        assert_eq!(st.c_w.value, Some(0.0));
    }
    assert_eq!(r.if_icp_thermal_v1.assignments[0].keys["P_icp_collector_bias_W"].value, Some(0.0));
}

#[test]
fn lc11_predictive_coupling_is_not_admissible_before_ver03() {
    // EQ-14 (from memory, VER-03) is a status gate in v1: no R_p(n_e) is computed, so LC-11 cannot be exercised and
    // CM-PRED produces no admissible number.
    let m = model();
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.coupling_mode = abep_icp::case::CouplingMode::Predictive;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::NotEvaluated);
    for v in ["VER-03", "VER-04", "VER-05", "VER-13"] {
        assert!(r.reason_codes().contains(&format!("CM-PRED_NOT_ADMISSIBLE:{v}")), "{v}");
    }
    assert!(r.reason_codes().contains("IN-09_ANTENNA_GEOMETRY_NOT_REGISTERED"));
    for k in ["R_p_ohm", "X_ant_ohm", "eta_p", "n_e_m3", "I_e_cap_A"] {
        assert!(r.scalar(k).value.is_none(), "{k}");
    }
    assert!(r.flags.contains("UNCALIBRATED_PREDICTIVE"));
}
