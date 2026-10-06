//! Statewise T - D over the 196 required design states (SC-WP-04, A9.29 sec. 9 / CLAUDE.md rule 9): missing physical
//! evidence is asserted as the fail-closed status, never skipped. The empty credible Hall transport set is an expected
//! governed state and is asserted explicitly.

use abep_mission::intake_drag::{load_drag_table, INTAKE_DRAG_LABEL};
use abep_mission::objective::{thrust_minus_drag, HallResponseStatus, NOT_EVALUATED};
use abep_mission::statewise_td::{
    statewise_t_minus_d, DesignPoint, CREDIBLE_HALL_TRANSPORT_SET_EMPTY, HOST_SPACECRAFT_DRAG_ICD_ABSENT,
};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::Value;
use abep_types::EvalStatus;

const SCENARIOS: [&str; 10] = [
    "maxwell_a0",
    "maxwell_a0.2",
    "maxwell_a0.5",
    "maxwell_a0.8",
    "maxwell_a1",
    "cll_a0",
    "cll_a0.2",
    "cll_a0.5",
    "cll_a0.8",
    "cll_a1",
];

fn s<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().and_then(|d| d.get(k)).unwrap_or(&Value::Null)
}

#[test]
fn credible_hall_transport_set_is_empty() {
    let hall = HallResponseStatus::load(&workspace_repo_root().unwrap()).unwrap();
    assert!(hall.admitted_members.is_empty(), "the governed credible set is EMPTY until an admission is recorded");
    assert_eq!(hall.credible_set(), "EMPTY");
}

#[test]
fn every_required_state_is_not_evaluated_with_the_registered_reasons() {
    let root = workspace_repo_root().unwrap();
    let (table, atm) = load_drag_table(&root).unwrap();
    assert_eq!(table.len(), 15760);
    assert_eq!(atm.ids.len(), 197);
    assert_eq!(atm.required_ids.len(), 196);
    assert!(table.entries.iter().all(|e| e.drag_per_area_n_m2.is_finite() && e.drag_per_area_n_m2 > 0.0));
    let hall = HallResponseStatus::load(&root).unwrap();
    for sc in SCENARIOS {
        for (a, ld, phi) in [(0.25, 3.0, 0.8), (1.0, 10.0, 0.9), (1.5, 20.0, 0.8)] {
            let p = DesignPoint { area_m2: a, l_over_d: ld, phi, scenario: sc.to_string() };
            let r = statewise_t_minus_d(&table, &hall, &p, &atm.required_ids).unwrap();
            assert_eq!((r.n_states, r.n_t_minus_d_evaluated, r.credible_set), (196, 0, "EMPTY"));
            for st in &r.states {
                assert_eq!(st.thrust.status, EvalStatus::NotEvaluated);
                assert_eq!(st.thrust.reason_key, CREDIBLE_HALL_TRANSPORT_SET_EMPTY);
                assert!(st.thrust.reason.starts_with("credible Hall transport set EMPTY"));
                assert_eq!(st.drag_body.status, EvalStatus::NotEvaluated);
                assert_eq!(st.drag_body.reason_key, HOST_SPACECRAFT_DRAG_ICD_ABSENT);
                assert_eq!(st.drag_intake.status, EvalStatus::IncompleteEvidence);
                assert_eq!(st.drag_intake.label, INTAKE_DRAG_LABEL);
                assert!(st.drag_intake.value_n.is_finite() && st.drag_intake.value_n > 0.0);
                assert_eq!(st.t_minus_d_status, EvalStatus::NotEvaluated);
                assert_eq!(s(&st.objective, "status").as_str(), Some(NOT_EVALUATED));
                assert_eq!(s(&st.objective, "value"), &Value::Null);
                let reason = s(&st.objective, "reason").as_str().unwrap();
                assert!(reason.contains("credible set EMPTY") && reason.contains("F1-ID-08"), "{reason}");
                let partial = s(&st.objective, "partial");
                assert_eq!(s(partial, "D_intake_status").as_str(), Some("PARAMETRIC_SENSITIVITY_ONLY"));
            }
        }
    }
}

#[test]
fn a_measured_thrust_record_is_refused_while_the_set_is_empty() {
    let hall = HallResponseStatus::load(&workspace_repo_root().unwrap()).unwrap();
    let rec = |v: f64| abep_types::pydict! { "value" => v, "evidence_class" => "measured", "source" => "test" };
    let o =
        thrust_minus_drag(&Value::Float(0.004), &Value::Null, &rec(0.03), &rec(0.002), &hall, &Value::Null).unwrap();
    assert_eq!(s(&o, "status").as_str(), Some(NOT_EVALUATED));
    assert_eq!(s(&o, "value"), &Value::Null);
    assert!(s(&o, "reason").as_str().unwrap().contains("credible Hall set is EMPTY"));
}

#[test]
fn a_point_outside_the_f1_design_space_is_out_of_domain() {
    let root = workspace_repo_root().unwrap();
    let (table, atm) = load_drag_table(&root).unwrap();
    let hall = HallResponseStatus::load(&root).unwrap();
    let p = DesignPoint { area_m2: 0.5, l_over_d: 7.0, phi: 0.9, scenario: "maxwell_a0".into() };
    let e = statewise_t_minus_d(&table, &hall, &p, &atm.required_ids).unwrap_err();
    assert_eq!(e.status(), EvalStatus::OutOfDomain);
    assert!(statewise_t_minus_d(&table, &hall, &p, &[]).is_err());
}
