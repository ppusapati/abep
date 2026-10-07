//! F8 pipeline invariants on a small registered sub-grid (contract PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1
//! INV-F8-01 .. INV-F8-05; diagnostic acceptance AT-09).

use abep_design::inputs::{load_upstream_inputs, UpstreamInputs};
use abep_uq::interp_sensitivity::{chain_application, Diagnostic};
use abep_uq::mc::tpmc_monte_carlo;
use abep_uq::robust::{require_all_admitted_scenarios, NOMINAL_WALL};
use abep_uq::study::{carried_value, f8_value, robust_decomposition, stage_f7, stage_f8, StudySpec};
use std::path::PathBuf;
use std::sync::OnceLock;

fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

fn inp() -> &'static UpstreamInputs {
    static I: OnceLock<UpstreamInputs> = OnceLock::new();
    I.get_or_init(|| load_upstream_inputs(&repo()).expect("upstream inputs"))
}

fn spec() -> StudySpec {
    StudySpec {
        candidates: Some(vec!["A1_Ld10_phi0.9".into(), "A1.5_Ld20_phi0.9".into()]),
        compressors: Some(vec![inp().compressor_ids[0].clone(), inp().compressor_ids[1].clone()]),
        n_mc: 3,
        sensitivity_fractions: vec![0.0],
    }
}

#[test]
fn inputs_cover_every_state_scenario_and_candidate() {
    let i = inp();
    assert_eq!(i.states.len(), 197);
    assert_eq!(i.required_states.len(), 196);
    assert_eq!(i.states[0], "h200_f150");
    assert_eq!(i.scenarios.len(), 10);
    assert_eq!(i.candidates.len(), 48);
    assert_eq!(i.compressor_ids.len(), 55);
    assert_eq!(i.filter_ids.len(), 5);
    assert_eq!(i.records.len(), 48 * 10 * 197);
}

#[test]
fn f8_pipeline_invariants_and_diagnostic_invariance() {
    let s = spec();
    let f7 = stage_f7(inp(), &s, &mut |_, _| {}).expect("F7");
    assert_eq!(f7.pareto.len(), 100);
    let a = stage_f8(&repo(), inp(), &f7, &s).expect("F8");
    // INV-F8-01: the evidence-gate snapshot is unchanged by the robust filter
    assert_eq!(a.gates_before, a.gates_after);
    assert_eq!(a.gates_before["hall_credible_set"], "EMPTY");
    // INV-F8-02: a robust member is feasible in every admitted scenario
    for b in &a.robust {
        for m in &b.members {
            let r = &a.scenario.iter().find(|(d, _)| *d == m.design_id).expect("scenario record").1;
            assert_eq!(r.n_scenarios_feasible, r.n_scenarios);
        }
    }
    // INV-F8-04: the carried set never yields a representative
    let carried = carried_value(&a, "test", "test").unwrap();
    assert!(carried["representative"].as_str().unwrap().starts_with("REFUSED RepresentativeSelectionRefused"));
    let dec = robust_decomposition(&a);
    assert_eq!(dec["n_survivors"], a.survivors.len());
    // AT-09 (diagnostic R-02): the F8 outputs are identical with the diagnostic computed in between
    let diag = Diagnostic::load(&repo()).unwrap();
    let cands: Vec<(String, f64, f64)> = vec![("A1_Ld10_phi0.9".into(), 10.0, 0.9)];
    let _ = chain_application(&diag, &cands, &inp().scenarios).unwrap();
    let b = stage_f8(&repo(), inp(), &f7, &s).expect("F8 again");
    assert_eq!(f8_value(&a), f8_value(&b));
}

#[test]
fn mc_draws_do_not_depend_on_batching() {
    // INV-F8-03: a candidate's records are identical alone and in a batch
    let s = spec();
    let f7 = stage_f7(inp(), &s, &mut |_, _| {}).expect("F7");
    let surv = abep_uq::robust::survivors(&f7.pareto, "F4-FIL-NONE", NOMINAL_WALL);
    if surv.len() >= 2 {
        let both = tpmc_monte_carlo(inp(), &surv[..2], &inp().scenarios, 2, NOMINAL_WALL).unwrap();
        let one = tpmc_monte_carlo(inp(), &surv[..1], &inp().scenarios, 2, NOMINAL_WALL).unwrap();
        for (k, v) in &one {
            assert_eq!(Some(v), both.get(k));
        }
    }
}

#[test]
fn robustness_requires_every_admitted_scenario() {
    let adm: Vec<String> = inp().scenarios.clone();
    let used = adm[..3].to_vec();
    let e = require_all_admitted_scenarios(&used, &adm, None).unwrap_err();
    assert_eq!(e.class, "A913RuleError");
    assert_eq!(e.status(), abep_types::EvalStatus::NotEvaluated);
    assert!(require_all_admitted_scenarios(&adm, &adm, None).is_ok());
}

#[test]
fn design_layer_never_depends_on_assessment_or_evidence() {
    for c in ["abep-design", "abep-uq", "abep-rng"] {
        let toml = std::fs::read_to_string(repo().join("crates").join(c).join("Cargo.toml")).unwrap();
        for forbidden in ["abep-assess", "abep-evidence", "abep-groundtest", "abep-cli"] {
            assert!(!toml.contains(forbidden), "{c} depends on {forbidden}");
        }
    }
}
