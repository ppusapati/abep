//! Headline numbers of the NP-ICP-NEUTRALIZER v1 verification suite, as JSON on stdout:
//! `cargo run -p abep-icp --example verification_table --locked`. The `cargo test` suite is the authoritative gate;
//! this only records the measured values for the verification reports (v1; v2 adds NV-06 with the direct side and the
//! registered-rate case). Every case is SYNTHETIC_TEST_ONLY; NV-06 compares registered rates only.

use abep_icp::case::{CouplingMode, RfInput};
use abep_icp::constants::{AMU, E_CHARGE, K_B, M_E};
use abep_icp::coupling;
use abep_icp::crosscheck::nv06_report;
use abep_icp::physics;
use abep_icp::testkit::*;
use abep_icp::{IcpModel, IcpResult};
use serde_json::{json, Value};
use std::f64::consts::PI;

fn v(r: &IcpResult, k: &str) -> f64 {
    r.scalar(k).value.unwrap_or(f64::NAN)
}

fn rel(a: f64, b: f64) -> f64 {
    if a == b {
        0.0
    } else {
        (a - b).abs() / a.abs().max(b.abs())
    }
}

fn max_closure(r: &IcpResult) -> f64 {
    let mut m: f64 = 0.0;
    for c in r.conservation.iter().chain(r.if_icp_thermal_v1.assignments.iter().flat_map(|a| a.closures.iter())) {
        if let Some(x) = c.value {
            m = m.max(x);
        }
    }
    for c in &r.if_icp_bus_v1.checks {
        if let Some(x) = c.value {
            m = m.max(x);
        }
    }
    m
}

fn main() {
    let m = IcpModel::load_workspace().expect("verified context");
    let sum_ha = H_EDGE * (2.0 * PI * R_M * L_M + 2.0 * PI * R_M * R_M);
    // LC-01 / LC-02.
    let rs: Vec<IcpResult> = [7.0, 70.0, 700.0].iter().map(|p| m.evaluate(&floating_case(*p))).collect();
    let n_g = 1.0 / (K_B * 300.0);
    let vol = PI * R_M * R_M * L_M;
    let f = |t: f64| n_g * 1e-13 * (-E_IZ_X_EV / t).exp() * vol - (E_CHARGE * t / (40.0 * AMU)).sqrt() * sum_ha;
    let (mut lo, mut hi) = (1.0f64, 20.0f64);
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        if f(mid) < 0.0 {
            lo = mid
        } else {
            hi = mid
        }
    }
    let t_ind = 0.5 * (lo + hi);
    let lc01 = rs.iter().map(|r| rel(v(r, "T_e_eV"), t_ind)).fold(0.0, f64::max);
    let lc02 = rs
        .iter()
        .zip([7.0, 70.0, 700.0])
        .map(|(r, p)| {
            let t = v(r, "T_e_eV");
            let ub = (E_CHARGE * t / (40.0 * AMU)).sqrt();
            let vs = 0.5 * t * (40.0 * AMU / (2.0 * PI * M_E)).ln();
            rel(v(r, "n_e_m3") / p, 1.0 / (E_CHARGE * ub * sum_ha * (E_IZ_X_EV + 2.5 * t + vs)))
        })
        .fold(0.0, f64::max);
    // LC-05 / LC-06.
    let sat = m.evaluate(&capoff_case(50.0, 0.0, 30.0));
    let lc05 = rel(v(&sat, "I_e_cap_A"), v(&sat, "I_e_thermal_limit_A"));
    let suite = [(0.0, 30.0), (0.0, 5.0), (-5.0, 10.0), (-10.0, 0.0), (0.0, 60.0)];
    let mut lc06 = (f64::NEG_INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY);
    for (a, b) in suite {
        let r = m.evaluate(&capoff_case(50.0, a, b));
        let cap = v(&r, "I_e_cap_A");
        lc06.0 = lc06.0.max(cap / v(&r, "I_e_thermal_limit_A"));
        lc06.1 = lc06.1.max(cap / v(&r, "I_ion_collection_limit_A"));
        lc06.2 = lc06.2.max(cap / v(&r, "I_production_A"));
    }
    let floating_cap = v(&m.evaluate(&floating_case(50.0)), "I_e_cap_A");
    // LC-07 / LC-08 / LC-09.
    let r = m.evaluate(&floating_case(20.0));
    let t = v(&r, "T_e_eV");
    let lc07 = rel(v(&r, "V_s_float_V"), 0.5 * t * (40.0 * AMU / (2.0 * PI * M_E)).ln());
    let flow0 = m.evaluate(&flow_case(0.0, 1e-7, 1.0));
    let vbar_x = (8.0 * K_B * 300.0 / (PI * M_X_KG)).sqrt();
    let lc09 = rel(flow0.map("n_g_m3")["X"].value.unwrap(), (1e-7 / M_X_KG) / (0.25 * vbar_x * 0.5 * PI * R_M * R_M));
    let n2 = &m.n2_set.species[m.n2_set.species_index("N2").unwrap()];
    let vbar_n2 = physics::neutral_mean_speed(293.0, n2.mass_kg);
    // Conservation over the case suite.
    let mut cal = capoff_case(0.0, 0.0, 30.0);
    cal.coupling_mode = CouplingMode::Calibrated;
    cal.rf_input = Some(RfInput::Forward { p_fwd_w: syn(200.0, "P_fwd"), p_refl_w: syn(10.0, "P_refl") });
    cal.coupling_evidence = Some(synthetic_p2(0.50, 0.30, 2.0, 3.0));
    cal.bus = Some(synthetic_bus(0.8, 0.9));
    let cases = vec![
        ("floating", floating_case(50.0)),
        ("capoff_saturated", capoff_case(50.0, 0.0, 30.0)),
        ("capoff_retarding", capoff_case(50.0, -5.0, 10.0)),
        (
            "excitation_bounding_pair",
            synthetic_case(
                "SYN_EXC",
                with_excitation(x_set(x_rate())),
                capoff_surfaces(),
                &[("ic", 0.0), ("ec", 30.0)],
                50.0,
            ),
        ),
        (
            "double_ion_nonlinear",
            synthetic_case(
                "SYN_X2",
                with_double_ion(x_set(x_rate())),
                capoff_surfaces(),
                &[("ic", 0.0), ("ec", 30.0)],
                50.0,
            ),
        ),
        ("flow_balance", flow_case(50.0, 1e-6, 0.8)),
        ("calibrated_with_bus", cal),
        ("zero_power", capoff_case(0.0, 0.0, 30.0)),
    ];
    let mut rows = Vec::new();
    for (name, c) in cases {
        let r = m.evaluate(&c);
        rows.push(json!({
            "case": name,
            "status": r.status,
            "plasma_state": r.plasma_state.value,
            "T_e_eV": r.scalar("T_e_eV").value,
            "n_e_m3": r.scalar("n_e_m3").value,
            "phi_p_V": r.scalar("phi_p_V").value,
            "I_e_cap_A": r.scalar("I_e_cap_A").value,
            "binding_limit": r.outputs["binding_limit"].label().and_then(|l| l.value.clone()),
            "max_conservation_or_closure_residual": max_closure(&r),
            "energy_balance_residual": r.convergence.energy_balance_residual,
            "quasi_neutrality_residual": r.convergence.quasi_neutrality_residual,
            "conservation": r.conservation.iter().map(|c| json!({"id": c.id, "status": c.status, "value": c.value})).collect::<Vec<Value>>(),
            "verify_items_on_path": r.verify_items_on_path,
        }));
    }
    // NV-06 / UQ-06: direct integral (EQ-06, abep_chem::checked) vs the 1 eV .dat interpolation, every AIR channel.
    let tes = [2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0];
    let nv = nv06_report(&m, &tes);
    let mut nv06 = Vec::new();
    for ch in &m.chem_registry.air.channels {
        let rows: Vec<_> = nv.iter().filter(|r| r.reaction == ch.id).collect();
        let rels: Vec<(f64, Option<f64>)> = rows.iter().map(|r| (r.t_e_ev, r.relative_difference.value)).collect();
        let on_row = |t: f64| (1.5 * t).fract() == 0.0;
        let max_abs = |pred: &dyn Fn(f64) -> bool| {
            rels.iter()
                .filter(|(t, _)| pred(*t))
                .filter_map(|(_, x)| x.map(f64::abs))
                .fold(None, |a: Option<f64>, x| Some(a.map_or(x, |a| a.max(x))))
        };
        nv06.push(json!({
            "channel": ch.id,
            "variant_role": ch.variant_role.as_str(),
            "direct_status": rows[0].direct_rate_m3_s.status,
            "direct_reasons": rows[0].direct_rate_m3_s.reasons,
            "max_abs_rel_on_table_rows": max_abs(&on_row),
            "max_abs_rel_between_rows": max_abs(&|t| !on_row(t)),
            "rel_at_T_e_eV": rels.iter().map(|(t, x)| json!([t, x])).collect::<Vec<Value>>(),
            "direct_k_m3_s_at_T_e_eV": rows.iter().map(|r| json!([r.t_e_ev, r.direct_rate_m3_s.value])).collect::<Vec<Value>>(),
        }));
    }
    // The registered-rate solve (SYNTHETIC_TEST_ONLY geometry and power; registered N2 channels).
    let ids = ["AIR-ION-03/ionization_N2_song2023", "AIR-EL-01/elastic_N2_song2023", "AIR-DIS-01/dissociation_N2"];
    let set = n2_registered_rate_set(&m, &ids, &["N2", "N", "N2^+"]);
    let rr = m.evaluate(&synthetic_case("SYN_N2_REGISTERED_RATES", set, floating_surfaces(), &[], 20.0));
    let registered_rate_case = json!({
        "status": rr.status,
        "plasma_state": rr.plasma_state.value,
        "T_e_eV": rr.equilibria.first().map(|e| e.t_e_ev),
        "n_e_m3": rr.equilibria.first().map(|e| e.n_e_m3),
        "scan_end_eV": rr.domain_checks.iter().find(|c| c.id == "IN-24_T_E_SCAN_END").and_then(|c| c.value),
        "reasons": rr.reason_codes(),
        "chemistry_validity": rr.chemistry_validity,
    });
    let (_, p_abs, q_coil) = coupling::antenna_split(185.0, 0.04, 0.0);
    let out = json!({
        "LC-01_max_rel_T_e_vs_independent_root": lc01,
        "LC-02_max_rel_n_e_over_P_abs": lc02,
        "LC-03_trivial_branch_rf_closure": coupling::trivial_branch(185.0, 0.36),
        "LC-04_eta_at_R_ant_0": coupling::coupling_efficiency(0.04, 0.0),
        "LC-04_Q_coil_at_R_ant_0": q_coil,
        "LC-04_P_abs_at_R_ant_0": p_abs,
        "LC-05_rel_I_e_cap_vs_thermal_limit_saturated": lc05,
        "LC-06_max_ratios_cap_over_thermal_ion_production": [lc06.0, lc06.1, lc06.2],
        "LC-06_all_floating_I_e_cap": floating_cap,
        "LC-07_rel_V_s": lc07,
        "LC-07_V_s_over_T_e_argon": v(&r, "V_s_float_V") / t,
        "LC-08_u_B_argon_3p5V": physics::bohm_speed(3.5, 1, 40.0 * AMU),
        "LC-08_h_R": physics::h_radial_lieberman(0.15, 0.03),
        "LC-08_h_L": physics::h_axial_lieberman(0.3, 0.03),
        "LC-09_rel_n_effusion": lc09,
        "LC-09_vbar_N2_293K": vbar_n2,
        "LC-09_C_prime_N2": 0.25 * vbar_n2,
        "cases": rows,
        "NV-06": nv06,
        "registered_rate_case": registered_rate_case,
        "abep_chem_admission": m.abep_chem_admission,
        "chem_registry": m.chem_registry_provenance(),
    });
    println!("{}", serde_json::to_string_pretty(&out).unwrap());
}
