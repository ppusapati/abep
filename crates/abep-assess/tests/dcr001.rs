//! DCR-DBF1-001 evaluation harness (docs/baseline/DCR-001/dcr001_eval_prereg_v1.json): preregistration pins, the
//! coefficient sets, the design-space axes, the steady chain's independence of the plenum volume, the DBF-1
//! reproduction of M2 v1 and the F1 drag cross-check, and the committed search selection re-evaluated.

use abep_assess::dcr001::*;
use abep_gaspath::compressor::DragCompressor;
use abep_provenance::{read_verified, workspace_repo_root};
use std::sync::OnceLock;

fn inputs() -> &'static Inputs {
    static I: OnceLock<Inputs> = OnceLock::new();
    I.get_or_init(|| gather(&workspace_repo_root().unwrap()).unwrap())
}

#[test]
fn prereg_pins_verify_and_a_wrong_pin_is_refused() {
    let repo = workspace_repo_root().unwrap();
    verify_prereg(&repo).unwrap();
    assert!(read_verified(&repo.join(PREREG_REL), &"0".repeat(64)).is_err());
}

#[test]
fn nominal_coefficients_are_the_code_defaults() {
    let d = DragCompressor::default();
    let mut c = DragCompressor { turbo_k_s: -1.0, eta_motor: -1.0, ..DragCompressor::default() };
    NOMINAL.apply(&mut c);
    assert_eq!(c, d);
}

#[test]
fn corners_cover_the_flow_band_ends_with_unfavourable_monotone_coefficients() {
    let cs = corners();
    assert_eq!(cs.len(), 8);
    let mut ids: Vec<_> = cs.iter().map(|c| c.0.clone()).collect();
    ids.sort();
    ids.dedup();
    assert_eq!(ids.len(), 8);
    for (_, c) in &cs {
        assert!(KS_BAND.contains(&c.turbo_k_s) && KK_BAND.contains(&c.turbo_k_k));
        assert!(LEAK_BAND.contains(&c.leak_conductance_m3_s));
        assert!(c.eta_motor < NOMINAL.eta_motor && c.p_ctrl_w > NOMINAL.p_ctrl_w);
        assert!(c.stator_mass_factor > NOMINAL.stator_mass_factor && c.motor_kg_per_nm > NOMINAL.motor_kg_per_nm);
        assert!(c.conductance_to_sink_w_k < NOMINAL.conductance_to_sink_w_k && c.t_sink_k > NOMINAL.t_sink_k);
    }
    assert_eq!(coefficient_sets()[0], ("NOMINAL".to_string(), NOMINAL));
}

#[test]
fn design_space_axes_match_the_preregistration() {
    let a = areas();
    assert_eq!(a.len(), 45);
    assert!(a.contains(&0.25) && a.contains(&0.6) && a.contains(&1.5));
    assert_eq!(GEOMS.len() * a.len(), 360);
    let inp = inputs();
    assert_eq!(inp.state_ids.len(), 196);
    assert_eq!(inp.up.scenarios.len(), 10);
    assert_eq!(inp.n_f3_grid, 2160);
    assert!(inp.compressors.iter().any(|c| c.id == inp.dbf1.upstream.compressor));
    assert_eq!((inp.t12_n, inp.t25_n, inp.drag_limit_n), (0.012, 0.025, 0.025));
    assert_eq!((inp.p_comp_limit_w, inp.m_comp_limit_kg), (250.0, 5.5));
}

#[test]
fn steady_chain_is_independent_of_the_plenum_volume() {
    let inp = inputs();
    let ie = eval_intake(inp, Intake { area: 0.31, g: 1 }).unwrap();
    let sd = sides(inp, &ie.intake, inp.filter(FILTERS[0]).unwrap()).unwrap();
    let plant = inp.plant(&inp.compressors[0], &NOMINAL).unwrap();
    let a = eval_triple(inp, &ie, &sd, &plant, &inp.plenum(VOLUMES_M3[0]).unwrap(), Mode::Full).unwrap();
    let b = eval_triple(inp, &ie, &sd, &plant, &inp.plenum(VOLUMES_M3[2]).unwrap(), Mode::Full).unwrap();
    assert_eq!(a, b);
}

#[test]
fn dbf1_reproduces_m2_and_drag_reproduces_f1() {
    let inp = inputs();
    let repo = workspace_repo_root().unwrap();
    assert_eq!(crosscheck_dbf1(inp, &repo).unwrap()["status"], "PASS");
    assert_eq!(crosscheck_f1_drag(inp).unwrap()["status"], "PASS");
}

#[test]
fn dbf1_fails_domain_in_the_low_accommodation_scenarios() {
    // BD-02: the DBF-1 point is out of domain (dead-head) in some admitted scenario; its compressor exceeds AL-02.
    let inp = inputs();
    let row = dbf1_row(inp).unwrap();
    let c = &row["nominal"]["criteria"];
    assert_eq!(c["C-DOMAIN"], false);
    assert_eq!(c["C-MASS"], false);
    assert!(row["nominal"]["rows_dead_head"].as_u64().unwrap() > 0);
}

#[test]
fn early_termination_never_changes_a_surviving_design() {
    let inp = inputs();
    let ie = eval_intake(inp, Intake { area: 0.25, g: 7 }).unwrap();
    let sd = sides(inp, &ie.intake, inp.filter(FILTERS[0]).unwrap()).unwrap();
    let plant = inp.up.plant(&inp.dbf1.upstream.compressor).unwrap().clone();
    let pl = inp.plenum(VOLUMES_M3[0]).unwrap();
    let full = eval_triple(inp, &ie, &sd, &plant, &pl, Mode::Full).unwrap();
    let nf = eval_triple(inp, &ie, &sd, &plant, &pl, Mode::NonFlow).unwrap();
    for (a, b) in full.iter().zip(&nf) {
        if b.complete {
            assert_eq!(a, b);
        } else {
            assert_ne!(flags(inp, a, ie.drag_ok).n_non_flow_failed(), 0);
        }
    }
}
