//! NP-HALL-PARAMETRIC-ENVELOPE addendum A5 (+ A5.1) in harness v2: the M2 intake closure under A9.35. Today's
//! evaluation of every registered design set, the analytic identities of the comparisons, the classification effect on
//! SYNTHETIC test-only inputs (DESIGN_VARIABLE_LIMIT, never PHYSICALLY_NON_CLOSING, CA4 first, scenario rule), fail-closed
//! inputs, pins and determinism. Every synthetic value carries SYNTHETIC_TEST_DATA_NOT_EVIDENCE semantics and never
//! enters a record.

use abep_assess::closure::{
    to_json, NOT_DETERMINABLE, PHYSICALLY_NON_CLOSING, PHYSICS_FEASIBLE, PHYSICS_NON_CLOSING,
    SELECT_WITH_EVIDENCE_CONDITIONS,
};
use abep_assess::closure_m1::conservation::{AreaLimit, A4_CONSERVATION_BOUND_NON_CLOSING};
use abep_assess::closure_m1::gather::gather_m1;
use abep_assess::closure_m1::intake::*;
use abep_assess::closure_m1::intake_record::{intake_record, record_block};
use abep_assess::closure_m1::{category_a2, classify_v2, evaluate, M1Inputs, M1Outcome};
use abep_mission::integration::Mode;
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::Value;
use abep_types::EvalStatus;
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn base() -> &'static M1Inputs {
    static B: OnceLock<M1Inputs> = OnceLock::new();
    B.get_or_init(|| gather_m1(&repo(), None, None, "test").unwrap())
}

fn base_out() -> &'static M1Outcome {
    static O: OnceLock<M1Outcome> = OnceLock::new();
    O.get_or_init(|| evaluate(base()).unwrap())
}

fn a5(o: &M1Outcome) -> &IntakeOutcome {
    o.a5.as_ref().unwrap()
}

fn inputs(i: &M1Inputs) -> &IntakeInputs {
    i.a5.as_ref().unwrap()
}

fn with_area(value_m2: f64, status: &str) -> M1Inputs {
    let mut inp = base().clone();
    inp.a4.as_mut().unwrap().area = AreaLimit::Registered {
        value_m2,
        status: status.into(),
        provenance: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
    };
    inp
}

/// SYNTHETIC: every captured and delivered flow scaled by `k` (in the scenarios `only`, or all).
fn scaled(k: f64, only: Option<&str>) -> M1Inputs {
    let mut inp = base().clone();
    let a = inp.a5.as_mut().unwrap();
    for cs in &mut a.capture {
        if only.is_none_or(|s| s == cs.scenario) {
            for r in &mut cs.rows {
                for x in &mut r.species_kg_s {
                    *x *= k;
                }
            }
        }
    }
    for m in &mut a.members {
        if only.is_none_or(|s| s == m.scenario) {
            for x in &mut m.mdot_del {
                *x *= k;
            }
        }
    }
    inp
}

fn air_a5(o: &M1Outcome) -> Vec<(&str, Option<&abep_assess::closure::Constraint>)> {
    o.states
        .iter()
        .filter(|(s, _)| s.required)
        .map(|(s, ms)| {
            (s.state_id.as_str(), ms[&Mode::AirPrimary].eval.constraints.iter().find(|c| c.id == A5_CONSTRAINT_ID))
        })
        .collect()
}

// ------------------------------------------------------------------------------------------------ today

#[test]
fn today_every_registered_design_set_is_evaluated_and_no_current_design_is_named() {
    let i = inputs(base());
    assert_eq!(i.states.len(), 196);
    assert_eq!(i.candidates.len(), 48, "F1 grid: 6 areas x 4 L/d x 2 phi (d collapsed, F1-02)");
    assert_eq!(i.scenarios.len(), 10);
    assert_eq!(i.capture.len(), 480);
    assert_eq!(i.members.len(), 1279, "every committed F7 Pareto member");
    assert!(i.robust_members.is_empty(), "F8 robust set EMPTY, carried unchanged");
    assert_eq!(i.f8_survivors.len(), 90);
    assert!(i.members.iter().all(|m| crosscheck_ok(m.mdot_delivered_min_rerun_kgps, m.mdot_delivered_min_kgps)));
    let o = a5(base_out());
    // F1-admissible intakes: the A = 0.25 m^2 candidates only (C-DRAG-RFP), 8 per scenario.
    for sc in &i.scenarios {
        let adm: Vec<&str> =
            o.cand_rows.iter().filter(|(r, _)| r.admissible && &r.scenario == sc).map(|(r, _)| r.id.as_str()).collect();
        assert_eq!(adm.len(), 8, "{sc}");
        assert!(adm.iter().all(|c| c.starts_with("A0.25_")));
    }
    assert!(o.cand_rows.iter().filter(|(r, _)| !r.admissible).all(|(r, _)| r.n_f1_infeasible_states > 0
        && r.f1_reason_example.as_deref().is_some_and(|x| x.contains("C-DRAG-RFP"))));
    assert!(o.excluded.is_empty() && o.flagged.is_empty(), "A4-REG-01 OPEN: no area limit, nothing excluded");
    let blk = record_block(base(), base_out()).unwrap();
    let d = blk.as_dict().unwrap();
    let di = d.get("design_identification").unwrap().as_dict().unwrap();
    assert_eq!(di.get("current_design").unwrap().as_str(), Some("NONE_SELECTED"));
}

#[test]
fn today_the_current_designs_miss_the_a4_necessary_condition_and_it_is_a_design_variable_limit() {
    let o = base_out();
    let r = a5(o);
    // Worst state of the A4 carry-forward (A9.35: 0.251 m^2 / 0.048 mg/s).
    let w = r.worst[&(Level::Area, 0)].unwrap();
    let st = &r.states[w.0];
    assert_eq!(st.state_id, "ds2:ECSS_LT_LOW:alt230:lat-84.0000:lst0:lon60:doy184");
    let q = st.req.unwrap();
    assert!((q.a_req[0] - 0.2511).abs() < 1e-4 && (q.mdot_req[0] - 4.796e-8).abs() < 1e-11);
    assert!(w.1.unwrap() > 1.0, "A = 0.25 m^2 < A_req(12 mN) at the worst state");
    for k in 0..2 {
        for l in Level::ALL {
            assert_eq!(r.one_hardware[&(l, k)].verdict, FAILS_IN_EVERY_SCENARIO, "{} {k}", l.as_str());
        }
    }
    // Cells: A5-NH-INTAKE wherever some level fails in every scenario; DESIGN_VARIABLE_LIMIT; never eligible.
    let cells = air_a5(o);
    assert!(!r.cells.is_empty());
    for (sid, c) in &cells {
        let s = r.states.iter().find(|x| x.state_id == *sid).unwrap();
        assert_eq!(c.is_some(), !s.cell_codes.is_empty(), "{sid}");
        if let Some(c) = c {
            assert!(!c.eligible_close && !c.eligible_non_close);
            assert_eq!(c.codes, s.cell_codes);
            assert!(c.codes.iter().all(|x| category_a2(x) == "DESIGN_VARIABLE_LIMIT"));
        }
    }
    // The classification stays C1 (no Hall envelope); A5 codes join the blocker list; XE untouched.
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C1"));
    let codes: BTreeSet<&str> = o.outcome.blockers.iter().map(|(c, _)| c.as_str()).collect();
    assert!(codes.contains(A5_DELIVERED_BELOW_REQUIRED_T12));
    for (_, ms) in &o.states {
        assert!(ms[&Mode::XeContingency].eval.constraints.iter().all(|c| c.id != A5_CONSTRAINT_ID));
    }
    // Without A5 the harness is the A2 + A4 harness: A4 unchanged, no A5 code.
    let mut inp = base().clone();
    inp.a5 = None;
    let o0 = evaluate(&inp).unwrap();
    assert_eq!(o0.a4, o.a4);
    assert!(o0.outcome.blockers.iter().all(|(c, _)| !c.starts_with("A5_")));
    assert_eq!(o0.outcome.step, o.outcome.step);
}

// ------------------------------------------------------------------------------------------------ analytic

#[test]
fn analytic_requirements_multipliers_and_efficiencies() {
    let r = a5(base_out());
    let t = r.t_req_n;
    for (n, s) in r.states.iter().enumerate() {
        let q = s.req.unwrap();
        // mdot_req,in at q = 0 is the A4 (A9.35) electric-power-only requirement; the inflow only lowers it.
        let mut q0 = q;
        q0.q_max = 0.0;
        for k in 0..2 {
            assert_eq!(q0.mdot_req_in(0.25, k, t).unwrap(), q.mdot_req[k]);
            assert!(q.mdot_req_in(0.25, k, t).unwrap() <= q.mdot_req[k]);
        }
        // The level verdict inverts the multipliers: FAILS iff every scenario's best k > 1 (or no design).
        for k in 0..2 {
            for l in Level::ALL {
                let ls = &s.levels[&(l, k)];
                let all_fail = ls.per_scenario.iter().all(|b| b.k.is_none_or(|x| x > 1.0));
                assert_eq!(ls.verdict == FAILS_IN_EVERY_SCENARIO, all_fail);
                assert_eq!(s.cell_codes.contains(&l.code(k).to_string()), all_fail);
                if let Some(kf) = ls.k_fav {
                    assert!(ls.per_scenario.iter().filter_map(|b| b.k).all(|x| x >= kf));
                }
            }
            // L-AREA multiplier is A_req / A.
            assert_eq!(s.levels[&(Level::Area, k)].k_fav, Some(q.a_req[k] / 0.25));
        }
        // Efficiencies of the best captured design.
        let (m, c, sc) = s.best_cap.clone().unwrap();
        let ci = inputs(base()).candidates.iter().position(|x| x.id == c).unwrap();
        let v = design_values(inputs(base()), r, ci, &sc, n).unwrap();
        assert_eq!(v.mdot_cap, m);
        assert!((v.a_cap_eq - m / q.phi_max).abs() <= 1e-15);
        assert!(v.eta_vs_bound <= v.eta_tot && v.eta_tot <= 1.0 + 1e-6, "Phi_max >= Phi_adm");
        assert!((v.species_mass_fraction.iter().sum::<f64>() - 1.0).abs() < 1e-12);
    }
}

#[test]
fn analytic_ideal_capture_gives_unit_efficiency_and_aperture_area() {
    // SYNTHETIC: a capture record equal to the free-stream O / N2 / O2 flux on A gives eta_c = 1; one equal to
    // Phi_max A gives A_cap,eq = A and eta_vs_bound = 1.
    let mut inp = base().clone();
    let o = a5(base_out());
    let i0 = 0;
    let q = o.states[i0].req.unwrap();
    let a = inp.a5.as_mut().unwrap();
    let c0 = a.capture.iter().position(|c| c.candidate == 0).unwrap();
    let area = a.candidates[0].area_m2;
    a.capture[c0].rows[i0].species_kg_s = [q.phi_3 * area, 0.0, 0.0];
    let o1 = evaluate(&inp).unwrap();
    let sc = inp.a5.as_ref().unwrap().capture[c0].scenario.clone();
    let v = design_values(inp.a5.as_ref().unwrap(), a5(&o1), 0, &sc, i0).unwrap();
    assert!((v.eta_c - 1.0).abs() < 1e-12);
    let a = inp.a5.as_mut().unwrap();
    a.capture[c0].rows[i0].species_kg_s = [q.phi_max * area, 0.0, 0.0];
    let o2 = evaluate(&inp).unwrap();
    let v = design_values(inp.a5.as_ref().unwrap(), a5(&o2), 0, &sc, i0).unwrap();
    assert!((v.a_cap_eq - area).abs() < 1e-12 && (v.eta_vs_bound - 1.0).abs() < 1e-12);
}

// ------------------------------------------------------------------------------------------------ classification

#[test]
fn a_set_meeting_the_necessary_condition_adds_nothing_and_establishes_nothing() {
    // SYNTHETIC: x100 capture and delivered flow and a FROZEN area limit above every A_req, so that every level passes
    // or (L-DEL) stays NOT_ESTABLISHED_ROBUST_SET_EMPTY: no A5 constraint, the classification is the A2 + A4 one.
    let mut inp = scaled(100.0, None);
    inp.a4.as_mut().unwrap().area =
        AreaLimit::Registered { value_m2: 2.2, status: "FROZEN".into(), provenance: "SYNTHETIC".into() };
    let a = inp.a5.as_mut().unwrap();
    for c in &mut a.candidates {
        c.area_m2 = 2.0;
    }
    for m in &mut a.members {
        m.area_m2 = 2.0;
    }
    let o = evaluate(&inp).unwrap();
    let r = a5(&o);
    assert!(r.cells.is_empty());
    assert!(air_a5(&o).iter().all(|(_, c)| c.is_none()));
    for s in &r.states {
        for k in 0..2 {
            assert_eq!(s.levels[&(Level::Cap, k)].verdict, PASSES_IN_EVERY_SCENARIO);
            assert_eq!(s.levels[&(Level::Del, k)].verdict, NOT_ESTABLISHED_ROBUST_SET_EMPTY, "robust set EMPTY");
        }
    }
    assert_eq!(r.one_hardware[&(Level::Cap, 0)].verdict, NECESSARY_CONDITION_MET_IN_EVERY_SCENARIO);
    assert_eq!(r.one_hardware[&(Level::Del, 0)].verdict, NOT_ESTABLISHED_ROBUST_SET_EMPTY);
    let mut no_a5 = inp.clone();
    no_a5.a5 = None;
    assert_eq!(o.outcome.blockers, evaluate(&no_a5).unwrap().outcome.blockers);
}

#[test]
fn a_scenario_dependent_level_adds_no_constraint() {
    // SYNTHETIC: only maxwell_a1 is scaled x100: L-CAP passes there and fails elsewhere -> SCENARIO_DEPENDENT.
    let o = evaluate(&scaled(100.0, Some("maxwell_a1"))).unwrap();
    let r = a5(&o);
    let base_fail: Vec<bool> =
        a5(base_out()).states.iter().map(|s| s.levels[&(Level::Cap, 1)].verdict == FAILS_IN_EVERY_SCENARIO).collect();
    assert!(base_fail.iter().any(|x| *x));
    for (s, was) in r.states.iter().zip(base_fail) {
        if was {
            assert_eq!(s.levels[&(Level::Cap, 1)].verdict, SCENARIO_DEPENDENT, "{}", s.state_id);
            assert!(!s.cell_codes.contains(&A5_CAPTURE_BELOW_REQUIRED_T25.to_string()));
        }
    }
}

#[test]
fn a_failing_design_blocks_select_and_never_makes_physically_non_closing() {
    // SYNTHETIC: every cell otherwise PHYSICS_FEASIBLE on one hardware; the A5 constraints alone keep the
    // classification NOT_DETERMINABLE (C4) with DESIGN_VARIABLE_LIMIT blockers; never C2.
    let o = base_out();
    let mut states = o.states.clone();
    let hw: BTreeSet<(String, String)> = [("SYN".to_string(), "SYN".to_string())].into();
    for (_, ms) in &mut states {
        for e in ms.values_mut() {
            e.eval.constraints.clear();
            e.eval.status = PHYSICS_FEASIBLE;
            e.eval.blockers.clear();
            e.joint_hardware = hw.clone();
        }
    }
    let feasible = classify_v2(true, true, &states);
    assert_eq!(feasible.classification, SELECT_WITH_EVIDENCE_CONDITIONS);
    apply_cells(a5(o), &mut states);
    let out = classify_v2(true, true, &states);
    assert_eq!((out.classification, out.step), (NOT_DETERMINABLE, "C4"));
    assert!(out.blockers.iter().all(|(c, _)| A5_CELL_CODES.contains(&c.as_str())));
    assert_eq!(
        out.blockers.iter().find(|(c, _)| c == A5_DELIVERED_BELOW_REQUIRED_T25).map(|x| x.1),
        Some(a5(o).cells.len()),
    );
}

#[test]
fn a_frozen_area_limit_excludes_larger_designs_and_ca4_decides_first() {
    // SYNTHETIC FROZEN limit 0.2 m^2: every candidate (A >= 0.25) is outside it, every level fails (no design), and
    // A4 CA4 fires because 0.2 < A_req(12 mN) at some state: PHYSICALLY_NON_CLOSING via CA4 only, A5 never eligible.
    let o = evaluate(&with_area(0.2, "FROZEN")).unwrap();
    let r = a5(&o);
    assert_eq!(r.excluded.len(), 48);
    assert_eq!((o.outcome.classification, o.outcome.step), (PHYSICALLY_NON_CLOSING, "CA4"));
    assert!(o.outcome.blockers.iter().all(|(c, _)| c == A4_CONSERVATION_BOUND_NON_CLOSING));
    for (sid, c) in air_a5(&o) {
        let c = c.unwrap_or_else(|| panic!("{sid}: no design inside the limit"));
        assert!(!c.eligible_non_close);
    }
    // PROVISIONAL: flagged, not excluded, never eligible.
    let o = evaluate(&with_area(0.2, "PROVISIONAL")).unwrap();
    assert!(a5(&o).excluded.is_empty() && a5(&o).flagged.len() == 48);
    assert_eq!(o.outcome.blockers, base_out().outcome.blockers);
    // A FROZEN limit at 0.6 m^2: no CA4 at T12 here only if A_req(12) <= 0.6 everywhere; the A5 cells stay
    // DESIGN_VARIABLE_LIMIT and the classification is never PHYSICALLY_NON_CLOSING through A5.
    let o = evaluate(&with_area(0.6, "FROZEN")).unwrap();
    assert!(o.outcome.step != "C2");
    if o.outcome.step != "CA4" {
        assert_ne!(o.outcome.classification, PHYSICALLY_NON_CLOSING);
        assert!(o.states.iter().all(|(_, ms)| ms[&Mode::AirPrimary].eval.status != PHYSICS_NON_CLOSING));
    }
}

// ------------------------------------------------------------------------------------------------ fail closed

#[test]
fn a_state_without_a4_inputs_is_not_evaluated_and_adds_nothing() {
    let mut inp = base().clone();
    let a4 = inp.a4.as_mut().unwrap();
    a4.states[0].wind_m_s = None;
    a4.states[0].codes.push("A4_WIND_NOT_AVAILABLE".into());
    let o = evaluate(&inp).unwrap();
    let s = &a5(&o).states[0];
    assert_eq!(s.status, EvalStatus::NotEvaluated);
    assert!(s.levels.is_empty() && s.cell_codes.is_empty());
    assert!(s.codes.contains(&"A4_WIND_NOT_AVAILABLE".to_string()));
    assert!(air_a5(&o)[0].1.is_none());
}

#[test]
fn crosscheck_tolerance_is_a5_1() {
    let x = 1.6148539559836865e-9;
    let up = |v: f64, n: u64| f64::from_bits(v.to_bits() + n);
    assert!(crosscheck_ok(x, x));
    assert!(crosscheck_ok(up(x, 1), x), "the 1-ulp case that refused under A5");
    assert!(crosscheck_ok(up(x, 4), x));
    assert!(!crosscheck_ok(x * (1.0 + 2e-9), x));
    assert!(!crosscheck_ok(f64::NAN, x));
    assert_eq!(ulp_distance(up(x, 3), x), 3);
    let big = 1e-3;
    assert!(crosscheck_ok(big * (1.0 + 5e-10), big), "r_rel 1e-9 dominates at larger values");
}

fn copy_into(tmp: &Path, rels: &[&str]) {
    for rel in rels {
        let dst = tmp.join(rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo().join(rel), dst).unwrap();
    }
}

#[test]
fn a5_and_a5_1_pins_are_verified() {
    let files = [A5_REL, A5_MD_REL, A5_LOCK_REL, A5_1_REL, A5_1_MD_REL, A5_1_LOCK_REL];
    let t = std::env::temp_dir().join(format!("abep_a5_pins_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&t);
    copy_into(&t, &files);
    verify_a5(&t).unwrap();
    for f in files {
        let p = t.join(f);
        let orig = std::fs::read(&p).unwrap();
        let mut b = orig.clone();
        let n = b.len();
        b[n / 2] ^= 1;
        std::fs::write(&p, b).unwrap();
        assert!(verify_a5(&t).is_err(), "{f}");
        std::fs::write(&p, orig).unwrap();
    }
    let _ = std::fs::remove_dir_all(&t);
}

#[test]
fn mismatched_state_lists_are_refused() {
    let mut inp = base().clone();
    inp.a5.as_mut().unwrap().states.swap(0, 1);
    assert!(evaluate(&inp).is_err());
}

// ------------------------------------------------------------------------------------------------ determinism

#[test]
fn the_a5_record_is_deterministic_and_carries_no_synthetic_value() {
    let a = to_json(&intake_record(base(), base_out(), "DET").unwrap()).unwrap();
    let o = evaluate(base()).unwrap();
    let b = to_json(&intake_record(base(), &o, "DET").unwrap()).unwrap();
    assert_eq!(a, b);
    assert!(!a.contains("SYNTHETIC"));
    let v = abep_types::pyjson::loads(&a).unwrap();
    let d = v.as_dict().unwrap();
    assert_eq!(d.get("schema").and_then(Value::as_str), Some(RECORD_SCHEMA));
    assert_eq!(d.get("states").and_then(Value::as_list).map(<[Value]>::len), Some(196));
    assert_eq!(d.get("f7_members").and_then(Value::as_list).map(<[Value]>::len), Some(1279));
}

// ------------------------------------------------------------------------------------------------ committed records

fn committed(name: &str) -> (String, String) {
    let rel = format!("{}/{name}", abep_assess::closure_m1::NP_DIR);
    let text = std::fs::read_to_string(repo().join(&rel)).unwrap();
    let v = abep_types::pyjson::loads(&text).unwrap();
    let commit = v.as_dict().unwrap().get("rust_commit").and_then(Value::as_str).unwrap().to_string();
    (text, commit)
}

#[test]
fn committed_record_is_the_a5_record_of_today() {
    let (text, commit) = committed("intake_closure_a5_v1.json");
    let mut inp = base().clone();
    inp.today.mission.provenance.rust_commit = commit;
    let out = evaluate(&inp).unwrap();
    let now = to_json(&intake_record(&inp, &out, "A5_INTAKE_CLOSURE_V1").unwrap()).unwrap();
    assert_eq!(now, text, "byte-identical regeneration");
    assert!(!text.contains("SYNTHETIC"));
}

#[test]
fn committed_dry_run_v2_is_the_harness_v2_record_of_today() {
    let (text, commit) = committed("closure_run_m1_dryrun_v2.json");
    let mut inp = base().clone();
    inp.today.mission.provenance.rust_commit = commit;
    let out = evaluate(&inp).unwrap();
    let now = to_json(&abep_assess::closure_m1::record::record_v2(&inp, &out, "M1_DRY_RUN_NOT_DECISIVE")).unwrap();
    assert_eq!(now, text, "byte-identical regeneration");
    let v = abep_types::pyjson::loads(&text).unwrap();
    let c = v.as_dict().unwrap().get("classification").unwrap().as_dict().unwrap();
    assert_eq!(c.get("result").and_then(Value::as_str), Some(NOT_DETERMINABLE));
    assert_eq!(c.get("procedure_step").and_then(Value::as_str), Some("C1"));
    assert!(v.as_dict().unwrap().get("intake_closure_a5").unwrap().as_dict().unwrap().contains_key("addendum_a5"));
    assert!(!text.contains("SYNTHETIC"));
}
