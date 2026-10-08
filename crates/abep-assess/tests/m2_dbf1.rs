//! Addendum A8: the M2 evaluation of the DBF-1 design point. Synthetic cases carry
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE semantics and never enter a record.

use abep_assess::closure::{to_json, NON_CLOSING, NOT_DETERMINABLE, NOT_EVALUATED};
use abep_assess::closure_m1::dbf1::*;
use abep_assess::closure_m1::dbf1_record::record_dbf1;
use abep_assess::closure_m1::intake::{FAILS_IN_EVERY_SCENARIO, PASSES_IN_EVERY_SCENARIO, SCENARIO_DEPENDENT};
use abep_assess::closure_m1::FEED_LOOP_UNSTABLE_EQUILIBRIUM;
use abep_types::pyjson::Value;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const REF_REL: &str = "docs/milestones/M2_196_state_rfp_closure/dbf1_feed_stability_python_reference_v1.json";

fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().unwrap()
}

fn ref_sha() -> String {
    abep_provenance::sha256_hex(&std::fs::read(repo().join(REF_REL)).unwrap())
}

fn today() -> &'static (Dbf1Inputs, Dbf1Outcome) {
    static T: OnceLock<(Dbf1Inputs, Dbf1Outcome)> = OnceLock::new();
    T.get_or_init(|| {
        let inp = gather_dbf1(&repo(), Path::new(REF_REL), &ref_sha(), "test").unwrap();
        let out = evaluate_dbf1(&inp).unwrap();
        (inp, out)
    })
}

// ------------------------------------------------------------------------------------------------ synthetic

fn state(levels: Vec<((Lvl, usize), &'static str)>, ood: &[&str], unstable: &[&str]) -> StateA8 {
    StateA8 {
        levels: levels
            .into_iter()
            .map(|(k, v)| (k, LevelEval { verdict: v, k: vec![], k_fav: None, k_unfav: None }))
            .collect::<BTreeMap<_, _>>(),
        mdot_req_in: [None, None],
        mdot_req_in_td: vec![],
        a_req_td: vec![],
        ood_scenarios: ood.iter().map(|s| s.to_string()).collect(),
        unstable_scenarios: unstable.iter().map(|s| s.to_string()).collect(),
        mdot_del_range: None,
        compressor_min_w: None,
    }
}

#[test]
fn a_failing_dbf1_condition_is_a_design_variable_limit_never_eligible() {
    let s = state(vec![((Lvl::Del, 0), FAILS_IN_EVERY_SCENARIO), ((Lvl::Area, 2), PASSES_IN_EVERY_SCENARIO)], &[], &[]);
    let c = a8_constraint(&s);
    assert_eq!((c.status, c.eligible_non_close, c.eligible_close), (NON_CLOSING, false, false));
    assert_eq!(c.codes, ["A8_DBF1_DELIVERED_BELOW_REQUIRED_T12"]);
    assert_eq!(category_a8(&c.codes[0]), "DESIGN_VARIABLE_LIMIT");
    assert_eq!(blocker_type(&c.codes[0]), "design-variable");
}

#[test]
fn a_met_condition_establishes_nothing_and_stays_open() {
    let c = a8_constraint(&state(vec![((Lvl::Cap, 1), PASSES_IN_EVERY_SCENARIO)], &[], &[]));
    assert_eq!((c.status, c.eligible_close), ("OPEN", false));
    assert_eq!(c.codes, [A8_MET_NOTHING_ESTABLISHED]);
    let c = a8_constraint(&state(vec![((Lvl::Cap, 1), SCENARIO_DEPENDENT)], &[], &[]));
    assert_eq!(c.codes, [A8_SCENARIO_DEPENDENT]);
    let c = a8_constraint(&state(vec![], &[], &[]));
    assert_eq!(c.codes, [A8_A4_NOT_EVALUATED]);
}

#[test]
fn nh_flow_rules_for_the_frozen_design() {
    let c = nh_flow_dbf1(&state(vec![], &["cll_a0"], &["cll_a1"]));
    assert_eq!((c.status, c.codes.as_slice()), ("OPEN", [A8_GAS_PATH_OUT_OF_DOMAIN.to_string()].as_slice()));
    let c = nh_flow_dbf1(&state(vec![], &[], &["cll_a1"]));
    assert_eq!((c.status, c.eligible_non_close), (NON_CLOSING, false));
    assert_eq!(c.codes, [FEED_LOOP_UNSTABLE_EQUILIBRIUM]);
    let c = nh_flow_dbf1(&state(vec![], &[], &[]));
    assert!(c.codes.contains(&HALL_NUMERICS_NOT_CONVERGED.to_string()));
}

#[test]
fn no_a8_code_is_a_fundamental_limit() {
    for c in [
        HALL_NUMERICS_NOT_CONVERGED,
        A8_GAS_PATH_OUT_OF_DOMAIN,
        A8_ANODE_MATERIAL,
        A8_MET_NOTHING_ESTABLISHED,
        A8_SCENARIO_DEPENDENT,
        A8_A4_NOT_EVALUATED,
        HOST_DRAG_REFERENCE,
    ]
    .into_iter()
    .map(str::to_string)
    .chain((0..3).flat_map(|t| Lvl::ALL.map(|l| level_code(l, t))))
    {
        assert_ne!(category_a8(&c), "FUNDAMENTAL_ARCHITECTURE_LIMIT", "{c}");
    }
    assert_eq!(blocker_type(HALL_NUMERICS_NOT_CONVERGED), "model-numerics");
}

#[test]
fn the_icp_geometry_is_the_frozen_tube() {
    let cfg = abep_config::baseline::load_dbf1(&repo()).unwrap();
    let g = icp_geometry(&cfg);
    assert!(abep_icp::v2::evaluate::geometry_v2_violations(&g.value).is_empty());
    assert!(g.evidence.missing_attributes().is_empty());
    let area: f64 = g.value.surfaces.iter().filter(|s| !s.kind.is_open()).map(|s| s.area_m2).sum();
    assert!((area - 2.0 * std::f64::consts::PI * 0.06 * 0.15).abs() < 1e-15);
}

#[test]
fn a8_and_dbf1_pins_are_verified() {
    verify_a8(&repo()).unwrap();
}

#[test]
fn a_stability_reference_of_another_design_or_with_duplicates_is_refused() {
    let cfg = abep_config::baseline::load_dbf1(&repo()).unwrap();
    let text = std::fs::read_to_string(repo().join(REF_REL)).unwrap();
    let v = abep_types::pyjson::loads(&text).unwrap();
    let (rows, _) = parse_stability(&v, &cfg).unwrap();
    assert_eq!(rows.len(), 1960);
    let other = abep_types::pyjson::loads(&text.replace(&cfg.upstream.design_id, "OTHER")).unwrap();
    assert!(parse_stability(&other, &cfg).is_err());
    let mut dup = v.clone();
    if let Value::Dict(d) = &mut dup {
        if let Some(Value::List(r)) = d.get_mut("rows") {
            let first = r[0].clone();
            r.push(first);
        }
    }
    assert!(parse_stability(&dup, &cfg).is_err());
}

// ------------------------------------------------------------------------------------------------ repository

#[test]
fn today_m2_is_not_determinable_at_c1_with_hall_numerics_first() {
    let (inp, out) = today();
    assert_eq!((out.outcome.classification, out.outcome.step), (NOT_DETERMINABLE, "C1"));
    let hb = out.outcome.blockers.iter().find(|b| b.0 == HALL_NUMERICS_NOT_CONVERGED).unwrap();
    assert_eq!(hb.1, 2 * inp.base.today.states.iter().filter(|s| s.required).count());
    assert!(!out.outcome.blockers.iter().any(|b| b.0 == "HALL_ENVELOPE_NOT_RUN"));
    assert_eq!((inp.stability.n_rows, inp.stability.n_agree), (1960, 1960));
}

#[test]
fn no_hall_value_enters_and_no_a8_constraint_is_eligible() {
    let (_, out) = today();
    for (_, ms) in &out.states {
        for (m, c) in ms {
            for h in &c.eval.hall {
                assert_eq!(h.constraint.status, NOT_EVALUATED);
                assert_eq!(h.constraint.codes, [HALL_NUMERICS_NOT_CONVERGED]);
                assert!(h.best_margin_n.is_none() && h.min_pbus_fav_w.is_none() && h.n_points == 0);
            }
            for x in &c.eval.eval.constraints {
                if x.codes.iter().any(|k| k.starts_with("A8_")) {
                    assert!(!x.eligible_non_close && !x.eligible_close, "{}", x.id);
                }
            }
            let has_a8 = c.eval.eval.constraints.iter().any(|x| x.id == A8_CONSTRAINT_ID);
            assert_eq!(has_a8, *m == abep_mission::integration::Mode::AirPrimary);
        }
    }
}

#[test]
fn the_dbf1_rerun_reproduces_the_committed_f7_minimum_where_it_is_a_member() {
    let (inp, _) = today();
    let covered: Vec<&str> =
        inp.scenarios.iter().filter(|s| s.committed_min.is_some()).map(|s| s.scenario.as_str()).collect();
    assert_eq!(covered, ["maxwell_a0.5", "maxwell_a0.8", "maxwell_a1", "cll_a0.5", "cll_a0.8", "cll_a1"]);
    for s in &inp.scenarios {
        assert_eq!(s.points.len(), 196);
    }
}

#[test]
fn the_record_is_deterministic_and_carries_no_synthetic_value() {
    let (inp, out) = today();
    let a = to_json(&record_dbf1(inp, out, "TEST").unwrap()).unwrap();
    let out2 = evaluate_dbf1(inp).unwrap();
    let b = to_json(&record_dbf1(inp, &out2, "TEST").unwrap()).unwrap();
    assert_eq!(a, b);
    assert!(!a.contains("SYNTHETIC"));
}

#[test]
fn a_python_rust_class_disagreement_is_refused() {
    let text = std::fs::read_to_string(repo().join(REF_REL)).unwrap();
    let i = text.find("\"class\": \"S\"").unwrap();
    let bad = format!("{}\"class\": \"U\"{}", &text[..i], &text[i + "\"class\": \"S\"".len()..]);
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(format!("m2_dbf1_{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let p = dir.join("ref.json");
    std::fs::write(&p, &bad).unwrap();
    let sha = abep_provenance::sha256_hex(bad.as_bytes());
    let e = gather_dbf1(&repo(), &p, &sha, "test").err().expect("refused");
    assert!(e.to_string().contains("R2"), "{e}");
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn committed_m2_record_is_the_a8_record_of_today() {
    let rel = "docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json";
    let text = std::fs::read_to_string(repo().join(rel)).unwrap();
    let v = abep_types::pyjson::loads(&text).unwrap();
    let commit = v.as_dict().unwrap().get("rust_commit").and_then(Value::as_str).unwrap().to_string();
    let mut inp = today().0.clone();
    inp.base.today.mission.provenance.rust_commit = commit;
    let out = evaluate_dbf1(&inp).unwrap();
    let now = to_json(&record_dbf1(&inp, &out, "M2_DBF1_V1").unwrap()).unwrap();
    assert_eq!(now, text, "byte-identical regeneration");
    let c = v.as_dict().unwrap().get("classification").unwrap().as_dict().unwrap();
    assert_eq!(c.get("result").and_then(Value::as_str), Some(NOT_DETERMINABLE));
    assert_eq!(c.get("procedure_step").and_then(Value::as_str), Some("C1"));
}
