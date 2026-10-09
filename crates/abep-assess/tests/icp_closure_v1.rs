//! A9.38 P4 RF/ICP neutralizer closure record (registration ICP-CLOSURE-REG-v1): byte-identical regeneration,
//! independent closed forms of the bounds, the literal closure-state rule and fail-closed capacity reporting.

use abep_assess::closure_icp::*;
use abep_icp::constants::{AMU, E_CHARGE};
use abep_icp::geometry::HModel;
use abep_icp::v2::case::NeutralSourceV2;
use abep_types::pyjson::Value;
use std::path::PathBuf;
use std::sync::OnceLock;

fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

fn record() -> &'static (Value, String) {
    static R: OnceLock<(Value, String)> = OnceLock::new();
    R.get_or_init(|| {
        let v = build(&repo()).expect("ICP closure record builds");
        let t = render(&v).expect("renders");
        (v, t)
    })
}

fn at<'a>(v: &'a Value, path: &[&str]) -> &'a Value {
    path.iter().fold(v, |x, k| x.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("missing {k}")))
}

fn strs(v: &Value) -> Vec<String> {
    match v {
        Value::List(l) => l.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
        _ => panic!("not a list"),
    }
}

#[test]
fn committed_icp_closure_record_is_the_record_of_today() {
    let committed = std::fs::read_to_string(repo().join(RECORD_REL)).expect("committed record");
    assert_eq!(record().1, committed, "byte-identical regeneration of {RECORD_REL}");
    // Deterministic: a second build renders the same bytes.
    assert_eq!(render(&build(&repo()).unwrap()).unwrap(), record().1);
}

#[test]
fn bounds_are_the_independent_closed_forms() {
    // B1 written out with SI values (e exact, u as the crate constant): T (e / (2 m V))^1/2.
    let ib = |t: f64, mu: f64, v: f64| t * (1.602_176_634e-19 / (2.0 * mu * 1.660_539_066_60e-27 * v)).sqrt();
    for (t, mu) in [(0.012, 31.99954), (0.025, 31.99954), (0.012, 131.299), (0.025, 131.299)] {
        let a = i_beam_lb(t, mu, 350.0);
        assert!(((a - ib(t, mu, 350.0)) / a).abs() <= 1e-14, "{t} {mu}");
    }
    assert_eq!(E_CHARGE, 1.602_176_634e-19);
    assert_eq!(AMU, 1.660_539_066_60e-27);
    // B3: P / E_iz (watts over volts).
    assert_eq!(i_e_cap_ub(500.0, 12.5), 40.0);
    // Monotone: heavier ions and higher V_d lower the bound; the record carries the heaviest ion and V_d,max.
    assert!(i_beam_lb(0.012, 31.99954, 350.0) < i_beam_lb(0.012, 15.99977, 350.0));
    assert!(i_beam_lb(0.012, 131.299, 350.0) < i_beam_lb(0.012, 131.299, 180.0));
    // B5 grows linearly with the flow.
    let p1 = p_greuse(1e-7, 15.99977, 300.0, 0.06);
    assert!((p_greuse(2e-7, 15.99977, 300.0, 0.06) / p1 - 2.0).abs() <= 1e-12);
}

#[test]
fn the_closure_state_rule_is_applied_literally_in_order() {
    assert_eq!(closure_state(false, true, true), STATE_DCR);
    assert_eq!(closure_state(true, true, true), STATE_CLOSED);
    assert_eq!(closure_state(true, false, true), STATE_CLOSED);
    assert_eq!(closure_state(true, true, false), STATE_FROZEN_EM);
    assert_eq!(closure_state(true, false, false), STATE_BLOCKED);
    let (v, _) = record();
    assert_eq!(at(v, &["closure", "state"]).as_str(), Some(STATE_BLOCKED));
    assert_eq!(at(v, &["closure", "conservation_feasible_in_frozen_envelope"]), &Value::Bool(true));
}

#[test]
fn a_withheld_capacity_never_carries_a_value_and_m_n_is_not_formed() {
    let (v, _) = record();
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY", "EM-N2"] {
        let r = at(v, &["model_evaluation_M_A", m]);
        assert_eq!(at(r, &["I_e_cap_converged_points"]), &Value::int(0), "{m}");
        assert_eq!(at(r, &["I_e_cap_envelope", "status"]).as_str(), Some("WITHHELD"));
        assert_eq!(at(r, &["reference_point", "I_e_cap_A"]), &Value::Null);
        assert_ne!(at(r, &["reference_point", "status"]).as_str(), Some("CONVERGED"));
        assert!(!strs(at(r, &["verify_items_on_path"])).contains(&"VER-25".to_string()));
    }
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
        let d = at(v, &["neutralization_M_D", m]);
        assert_eq!(at(d, &["hc05", "status"]).as_str(), Some("NOT_EVALUATED"));
        assert_eq!(at(d, &["hc05", "M_n"]), &Value::Null);
        assert_eq!(at(d, &["neutralization_quantities", "M_n_point"]), &Value::Null);
    }
    assert_eq!(at(v, &["neutralization_M_D", "GNG-ICP-01", "status"]).as_str(), Some("NOT_EVALUATED"));
    // The analog carries its labels and never enters the closure section.
    let labels = strs(at(v, &["analog_M_C", "XE_CONTINGENCY", "labels"]));
    assert!(labels.contains(&"ANALOG_ESTIMATE_NOT_A_MODEL_RESULT".to_string()));
    assert_eq!(at(v, &["analog_M_C", "AIR_PRIMARY", "status"]).as_str(), Some("NOT_EVALUATED"));
}

#[test]
fn the_registration_closes_the_non_chemistry_inputs_of_the_m2_icp_path() {
    let (v, _) = record();
    let xe = strs(at(v, &["inputs_vs_m2_p_icp_dbf1", "XE_CONTINGENCY", "closed_by_registration"]));
    for c in [
        "DOM-06_B_ICP_NOT_REGISTERED",
        "IN-08_RF_INPUT_NOT_REGISTERED",
        "IN-11_ELECTRODES_NOT_REGISTERED",
        "IN-12_NEUTRAL_SOURCE_NOT_REGISTERED",
        "IN-17_NO_EDGE_FACTOR_SOURCE",
    ] {
        assert!(xe.contains(&c.to_string()), "{c}");
    }
    // What remains for Xe is chemistry only.
    for c in strs(at(v, &["inputs_vs_m2_p_icp_dbf1", "XE_CONTINGENCY", "remaining"])) {
        assert!(c.contains("XE") || c.starts_with("CHG-04"), "{c}");
    }
    // AIR keeps the edge factor open (no O+ / O2+ source read) and nothing new appears in either mode.
    let air = strs(at(v, &["inputs_vs_m2_p_icp_dbf1", "AIR_PRIMARY", "remaining"]));
    assert!(air.contains(&"IN-17_NO_EDGE_FACTOR_SOURCE".to_string()));
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
        assert!(strs(at(v, &["inputs_vs_m2_p_icp_dbf1", m, "new_in_closure_case"])).is_empty(), "{m}");
    }
}

#[test]
fn every_case_carries_the_registered_inputs_with_complete_evidence() {
    let b = CaseBuilder::new(&repo()).unwrap();
    let grid = b.grid().unwrap();
    assert_eq!(grid.len(), 4 * 150 + 150 + 150);
    for m in ClosureMode::ALL {
        let c = b.case(&b.reference(m).unwrap()).unwrap();
        assert!(c.rf_input.is_some() && c.electrodes.is_some() && c.geometry.is_some());
        assert_eq!(c.b_icp_max_t.as_ref().map(|x| x.value), Some(0.0));
        let g = &c.geometry.as_ref().unwrap().value;
        assert_eq!(
            g.surfaces.iter().filter(|s| s.kind == abep_icp::geometry::SurfaceKind::ElectronCollector).count(),
            1
        );
        match (&c.h_model, m) {
            (None, ClosureMode::Air) => {}
            (Some(HModel::Lieberman { sigma_i_m2 }), ClosureMode::Xe) => assert!(sigma_i_m2.contains_key("Xe^+")),
            (Some(HModel::Lieberman { sigma_i_m2 }), ClosureMode::EmN2) => assert_eq!(sigma_i_m2.len(), 2),
            other => panic!("{other:?}"),
        }
        let Some(NeutralSourceV2::RegisteredPressure { mole_fractions, p_icp_pa, .. }) = &c.neutral_source else {
            panic!("REGISTERED_PRESSURE")
        };
        assert!((mole_fractions.value.values().sum::<f64>() - 1.0).abs() <= 1e-12);
        for e in [&p_icp_pa.evidence, &c.supply_mode.evidence, &c.electrodes.as_ref().unwrap().evidence] {
            assert!(e.missing_attributes().is_empty());
        }
    }
}

#[test]
fn committed_a1_collector_window_record_is_the_record_of_today() {
    let v = build_a1(&repo()).expect("A1 record builds");
    let committed = std::fs::read_to_string(repo().join(A1_RECORD_REL)).expect("committed A1 record");
    assert_eq!(render(&v).unwrap(), committed, "byte-identical regeneration of {A1_RECORD_REL}");
    // A parametric T_e never triggers the DBF1-ICP-04 DCR (A1 dcr_rule).
    assert_eq!(at(&v, &["dcr", "state"]).as_str(), Some("DCR_NOT_TRIGGERED_PENDING_EVIDENCE"));
}

#[test]
fn a1_sheath_relations_are_the_independent_closed_forms() {
    // E_floor / T_e = 1/2 + 1/2 ln(M / (2 pi m_e)); the P8 DA-03 table gives 4.655 (N+) and 5.774 (Xe+).
    let me = 9.109_383_713_9e-31;
    let fl = |mu: f64| 0.5 + 0.5 * (mu * 1.660_539_066_60e-27 / (2.0 * std::f64::consts::PI * me)).ln();
    for mu in [14.00643, 31.99806, 131.287] {
        assert!((floor_over_te(mu) - fl(mu)).abs() <= 1e-13);
    }
    assert!((floor_over_te(14.00643) - 4.655).abs() < 5e-4);
    assert!((floor_over_te(131.287) - 5.774).abs() < 5e-4);
    // f_max: no window at E* = E_floor; 1 - e^-1 one T_e above it.
    let te = 3.0;
    let e0 = te * floor_over_te(14.00643);
    assert_eq!(f_max(e0, te, 14.00643), None);
    assert!((f_max(e0 + te, te, 14.00643).unwrap() - (1.0 - (-1.0f64).exp())).abs() <= 1e-12);
    let ub = (1.602_176_634e-19_f64 * 3.0 / (14.00643 * 1.660_539_066_60e-27)).sqrt();
    assert!((u_bohm(3.0, 14.00643) - ub).abs() <= 1e-9 * ub);
}
