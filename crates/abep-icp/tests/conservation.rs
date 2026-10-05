//! Conservation checks CC-01..CC-07 (prereg `conservation_checks`; tolerance TOL-CONS = 1e-10 after a solve to 1e-12).
//! CLAUDE.md rule 4: source balances close exactly. No term is a remainder, so the checks test solve and bookkeeping.

mod common;

use abep_icp::case::{CouplingMode, Disposition, RfInput};
use abep_icp::constants::TOL_CONS;
use abep_icp::evidence::Registered;
use abep_icp::testkit::*;
use abep_icp::{IcpResult, IcpStatus};
use common::{model, val};

fn cc(r: &IcpResult, id: &str) -> (IcpStatus, Option<f64>) {
    let c = r.conservation.iter().find(|c| c.id == id).unwrap_or_else(|| panic!("{id} missing"));
    (c.status, c.value)
}

fn assert_closes(r: &IcpResult, id: &str) {
    let (s, v) = cc(r, id);
    assert_eq!(s, IcpStatus::Converged, "{id}: {v:?}");
    assert!(v.unwrap() <= TOL_CONS, "{id} = {v:?}");
}

fn cal_case(p_fwd: f64, p_refl: f64, eta_rf: f64) -> abep_icp::IcpCase {
    let mut c = synthetic_case(
        "SYN_CAL",
        with_excitation(x_set(x_rate())),
        capoff_surfaces(),
        &[("ic", 0.0), ("ec", 30.0)],
        0.0,
    );
    c.coupling_mode = CouplingMode::Calibrated;
    c.rf_input = Some(RfInput::Forward { p_fwd_w: syn(p_fwd, "P_fwd"), p_refl_w: syn(p_refl, "P_refl") });
    c.coupling_evidence = Some(synthetic_p2(0.50, 0.30, 2.0, 3.0));
    c.bus = Some(synthetic_bus(eta_rf, 0.9));
    c
}

#[test]
fn cc01_cc03_cc07_registered_pressure_single_and_multiply_charged() {
    let m = model();
    for case in [
        capoff_case(50.0, 0.0, 30.0),
        capoff_case(50.0, -5.0, 10.0),
        synthetic_case(
            "SYN_X2",
            with_double_ion(x_set(x_rate())),
            capoff_surfaces(),
            &[("ic", 0.0), ("ec", 30.0)],
            50.0,
        ),
    ] {
        let r = m.evaluate(&case);
        assert_eq!(r.status, IcpStatus::Converged, "{}: {:#?}", case.case_id, r.reasons);
        for id in ["CC-01", "CC-03", "CC-07"] {
            assert_closes(&r, id);
        }
        assert_eq!(cc(&r, "CC-02").0, IcpStatus::NotEvaluated, "REGISTERED_PRESSURE has no neutral balance");
    }
}

#[test]
fn cc01_cc02_flow_balance_with_plasma() {
    let r = model().evaluate(&flow_case(50.0, 1e-6, 0.8));
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    for id in ["CC-01", "CC-02", "CC-03", "CC-07"] {
        assert_closes(&r, id);
    }
    // Throughput: the feed leaves as neutrals and ions; conversion books mass only between species.
    let conv = &r.if_icp_feed_v1.dmdot_conversion_kg_s;
    let total: f64 = conv.values().map(val).sum();
    assert!(total.abs() <= 1e-12 * val(&conv["X"]).abs());
}

#[test]
fn cc04_cc05_cc06_calibrated_chain_partition_and_bus() {
    let r = model().evaluate(&cal_case(200.0, 10.0, 0.8));
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    assert_eq!(r.if_icp_thermal_v1.assignments.len(), 2, "UNRESOLVED excitation gives the bounding pair");
    for a in &r.if_icp_thermal_v1.assignments {
        for c in &a.closures {
            assert_eq!(c.status, IcpStatus::Converged, "{c:?}");
            if let Some(v) = c.value {
                assert!(v <= TOL_CONS, "{c:?}");
            }
        }
        assert!(a.closures.iter().any(|c| c.id.starts_with("CC-04")));
        assert!(a.closures.iter().any(|c| c.id.starts_with("CC-05-COMBINED")));
    }
    let b = &r.if_icp_bus_v1;
    assert_eq!(b.status, IcpStatus::Converged);
    assert_eq!(b.checks[0].status, IcpStatus::Converged);
    let slots: f64 = b.slots.values().map(val).sum();
    assert!((val(&b.keys["P_icp_bus_W"]) - slots).abs() <= TOL_CONS * slots);
    assert!(val(&b.keys["P_icp_rf_source_DC_W"]) >= val(&b.keys["P_icp_rf_forward_W"]));
    assert!(val(&b.keys["Q_icp_rf_generator_loss_W"]) >= 0.0 && val(&b.keys["Q_icp_bias_supply_loss_W"]) >= 0.0);
}

#[test]
fn cc06_violating_eta_rf_registration_is_refused() {
    // (P_fwd - P_refl) / eta_RF < P_fwd: the source would recover reflected power -> MODEL_ERROR.
    let r = model().evaluate(&cal_case(100.0, 20.0, 0.9));
    let b = &r.if_icp_bus_v1;
    assert!(b.reasons.contains(&"CC-06_RF_SOURCE_BELOW_FORWARD".to_string()), "{:?}", b.reasons);
    assert!(b.keys["P_icp_bus_W"].value.is_none());
    // An efficiency outside (0, 1] is refused at registration.
    let mut c = cal_case(200.0, 10.0, 0.8);
    c.bus.as_mut().unwrap().eta_rf = syn(1.2, "eta_RF");
    let r = model().evaluate(&c);
    assert_eq!(r.if_icp_bus_v1.status, IcpStatus::ModelError);
    assert!(r.if_icp_bus_v1.reasons.contains(&"CC-06_REGISTRATION_REFUSED".to_string()));
}

#[test]
fn cc05_every_bounding_assignment_closes_and_dispositions_route_energy() {
    let m = model();
    let set = with_excitation(x_set(x_rate()));
    let mut c = synthetic_case("SYN_EXC", set, capoff_surfaces(), &[("ic", 0.0), ("ec", 30.0)], 50.0);
    let r = m.evaluate(&c);
    let a: Vec<&str> = r.if_icp_thermal_v1.assignments.iter().map(|a| a.assignment.as_str()).collect();
    assert_eq!(a, vec!["ALL_RADIATED", "ALL_WALL"]);
    let rad = &r.if_icp_thermal_v1.assignments[0].keys;
    let wall = &r.if_icp_thermal_v1.assignments[1].keys;
    assert!(val(&rad["Q_icp_radiation_W"]) > 0.0);
    assert_eq!(wall["Q_icp_radiation_W"].value, Some(0.0));
    let moved = val(&wall["Q_icp_plasma_wall_W"]) - val(&rad["Q_icp_plasma_wall_W"]);
    assert!((moved - val(&rad["Q_icp_radiation_W"])).abs() <= 1e-12 * moved);
    assert!(r.flags.contains("AREA_WEIGHTED_NEUTRAL_TERMS"));
    // A registered disposition gives one assignment and puts VER-11 on the path.
    c.dispositions.insert("EXC_X".into(), Registered::synthetic(Disposition::RadiatedOpticallyThin, "disposition"));
    let r = m.evaluate(&c);
    assert_eq!(r.if_icp_thermal_v1.assignments.len(), 1);
    assert_eq!(r.if_icp_thermal_v1.assignments[0].assignment, "AS_REGISTERED");
    assert!(r.verify_items_on_path.contains("VER-11"));
}

#[test]
fn cc05_nodes_sum_to_the_plasma_wall_key() {
    let r = model().evaluate(&synthetic_case(
        "SYN_EXC",
        with_excitation(x_set(x_rate())),
        capoff_surfaces(),
        &[("ic", 0.0), ("ec", 30.0)],
        50.0,
    ));
    for a in &r.if_icp_thermal_v1.assignments {
        let nodes: f64 = a.q_icp_plasma_wall_by_node_w.values().map(val).sum();
        let total = val(&a.keys["Q_icp_plasma_wall_W"]);
        assert!((nodes - total).abs() <= 1e-12 * total, "{}: {nodes} vs {total}", a.assignment);
    }
}

#[test]
fn absorbed_power_without_a_sustained_state_breaches_cc05() {
    // No T_e root anywhere in the scanned domain while P_abs > 0: the imposed power has no sink (MODEL_ERROR).
    let mut c = capoff_case(50.0, 0.0, 30.0);
    if let abep_icp::chemistry::ChemistryRegistration::Synthetic { set } = &mut c.chemistry {
        set.reactions[0].rate = abep_icp::chemistry::RateSource::Synthetic { rate: arrhenius(1e-30, E_IZ_X_EV) };
    }
    let r = model().evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(r.reason_codes().contains("CC-05_ABSORBED_POWER_WITHOUT_SINK"));
    assert!(r.scalar("n_e_m3").value.is_none() && r.scalar("I_e_cap_A").value.is_none());
}
