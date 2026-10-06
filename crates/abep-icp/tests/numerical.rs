//! Numerical verification NV-01..NV-06 (prereg `numerical_verification`).

mod common;

use abep_chem::registry::Representation;
use abep_icp::chemistry::{RateSource, SyntheticRate};
use abep_icp::constants::{NUMERICS, TOL_SOLVE};
use abep_icp::crosscheck::{nv06_report, REPRESENTATION_NOT_REGISTERED};
use abep_icp::testkit::*;
use abep_icp::{IcpCase, IcpStatus};
use common::model;

fn cases() -> Vec<IcpCase> {
    vec![
        floating_case(25.0),
        capoff_case(50.0, 0.0, 30.0),
        capoff_case(0.0, 0.0, 30.0),
        synthetic_case(
            "SYN_X2",
            with_double_ion(x_set(x_rate())),
            capoff_surfaces(),
            &[("ic", 0.0), ("ec", 30.0)],
            50.0,
        ),
        flow_case(50.0, 1e-6, 0.8),
    ]
}

#[test]
fn nv01_double_run_byte_identity() {
    let m = model();
    for c in cases() {
        assert_eq!(m.evaluate(&c).to_json(), m.evaluate(&c).to_json(), "{}", c.case_id);
    }
}

#[test]
fn nv02_thread_count_independence() {
    let m = model();
    let reference: Vec<String> = cases().iter().map(|c| m.evaluate(c).to_json()).collect();
    let handles: Vec<_> = (0..4)
        .map(|_| std::thread::spawn(move || cases().iter().map(|c| model().evaluate(c).to_json()).collect::<Vec<_>>()))
        .collect();
    for h in handles {
        assert_eq!(h.join().expect("thread"), reference);
    }
}

#[test]
fn nv03_solver_and_conservation_residuals_are_reported() {
    let m = model();
    for c in cases() {
        let r = m.evaluate(&c);
        assert_eq!(r.status, IcpStatus::Converged, "{}: {:#?}", c.case_id, r.reasons);
        assert!(!r.conservation.is_empty(), "{}", c.case_id);
        if r.plasma_state.value.as_deref() == Some("SUSTAINED") {
            let cv = &r.convergence;
            for (n, x) in [
                ("species", cv.species_balance_residual),
                ("quasi", cv.quasi_neutrality_residual),
                ("current", cv.current_balance_residual),
                ("energy", cv.energy_balance_residual),
            ] {
                let x = x.unwrap_or_else(|| panic!("{}: {n} residual not reported", c.case_id));
                assert!(x <= TOL_SOLVE, "{}: {n} residual {x}", c.case_id);
            }
            assert!(cv.bisection_iterations.is_some());
            assert_eq!(cv.numerical_settings["t_e_scan_points"], NUMERICS.t_e_scan_points as f64);
        }
    }
}

#[test]
fn nv04_every_root_of_a_two_root_case_is_reported() {
    // k = k0 exp(-E/T_e - T_e/t_cut) rises and falls: the particle balance has two T_e roots.
    let rate = SyntheticRate { k0_m3_s: 1e-13, t_ref_ev: 1.0, power: 0.0, e_act_ev: E_IZ_X_EV, t_cut_ev: Some(8.0) };
    let c = synthetic_case("SYN_TWO_ROOT", x_set(rate), floating_surfaces(), &[], 20.0);
    let r = model().evaluate(&c);
    assert_eq!(r.equilibria.len(), 2, "{:#?}", r.equilibria);
    assert!(r.equilibria[0].t_e_ev < r.equilibria[1].t_e_ev);
    assert_eq!(r.status, IcpStatus::NotEvaluated);
    assert!(r.reason_codes().contains("EQUILIBRIUM_SELECTION_NOT_REGISTERED"));
    assert!(r.scalar("T_e_eV").value.is_none(), "no root is chosen silently");
}

#[test]
fn nv05_non_finite_values_give_model_error_with_null_values() {
    let mut c = capoff_case(50.0, 0.0, 30.0);
    if let abep_icp::chemistry::ChemistryRegistration::Synthetic { set } = &mut c.chemistry {
        set.reactions[0].rate = RateSource::Synthetic {
            rate: SyntheticRate { k0_m3_s: f64::NAN, t_ref_ev: 1.0, power: 0.0, e_act_ev: 15.0, t_cut_ev: None },
        };
    }
    let r = model().evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(r.reasons.iter().any(|x| x.code.starts_with("NV-05")), "{:#?}", r.reasons);
    for k in ["T_e_eV", "n_e_m3", "I_e_cap_A", "P_abs_W", "phi_p_V"] {
        assert!(r.scalar(k).value.is_none(), "{k}");
        assert_eq!(r.scalar(k).status, IcpStatus::ModelError, "{k}");
    }
    assert!(abep_icp::Quantity::value(f64::NAN, "W").value.is_none());
}

#[test]
fn nv06_direct_integral_vs_dat_reported_per_reaction() {
    let m = model();
    let air = &m.chem_registry.air;
    let tes = [2.0, 5.0, 10.0, 30.0];
    let rows = nv06_report(m, &tes);
    assert_eq!(rows.len(), air.channels.len() * tes.len());
    assert_eq!(air.channels.len(), 43);
    let mut evaluated = 0;
    for row in &rows {
        let dat = row.dat_rate_m3_s.value.expect("table defined at 3/2 T_e <= 45 eV");
        assert!(dat.is_finite() && dat >= 0.0, "{row:?}");
        let ch = air.channel(&row.reaction).unwrap();
        match &ch.representation {
            Representation::CrossSection { .. } => {
                // The direct side is the admitted integrator on the registered representation, bit for bit.
                let k = air.direct_rate(ch, row.t_e_ev).unwrap().k_m3_s;
                assert_eq!(row.direct_rate_m3_s.value.map(f64::to_bits), Some(k.to_bits()), "{}", row.reaction);
                let rel = row.relative_difference.value.expect("defined");
                assert_eq!(rel, (dat - k) / k);
                // On a table row (3/2 T_e = 3, 15, 45 eV) the .dat is the same integral printed to 7 digits.
                if row.t_e_ev != 5.0 && k > 1e-290 {
                    assert!(rel.abs() <= 5e-7, "{} at {} eV: {rel:e}", row.reaction, row.t_e_ev);
                }
                evaluated += 1;
            }
            Representation::NotRegistered { .. } => {
                let code = format!("{REPRESENTATION_NOT_REGISTERED}:{}", ch.id);
                assert_eq!(row.direct_rate_m3_s.status, IcpStatus::IncompleteEvidence);
                assert_eq!(row.direct_rate_m3_s.reasons, vec![code.clone()]);
                assert_eq!(row.relative_difference.status, IcpStatus::IncompleteEvidence);
                assert!(row.direct_rate_m3_s.value.is_none() && row.relative_difference.value.is_none());
            }
        }
    }
    assert_eq!(evaluated, 32 * tes.len());
    // The table cross-check reproduces the registered grid values (ionization_N2_song2023.dat, 3.0 eV row).
    let ion = rows.iter().find(|r| r.file == "ionization_N2_song2023.dat" && r.t_e_ev == 2.0).unwrap();
    assert_eq!(ion.dat_rate_m3_s.value, Some(4.436344e-18));
}
