//! NP-HALL-PARAMETRIC-ENVELOPE addendum A4 in harness v2: today's evaluation (no registered area limit: nothing
//! changes), the classification effect on SYNTHETIC test-only area limits (CA4 without any Hall envelope, the T25
//! existence rule, PROVISIONAL never eligible, XE never non-closing), fail-closed inputs, pins, determinism and the
//! committed record. Every synthetic value carries SYNTHETIC_TEST_DATA_NOT_EVIDENCE semantics and never enters a record.

use abep_assess::closure::{to_json, NOT_DETERMINABLE, PHYSICALLY_NON_CLOSING, PHYSICS_NON_CLOSING};
use abep_assess::closure_m1::conservation::*;
use abep_assess::closure_m1::conservation_record::{bounds_record, record_block};
use abep_assess::closure_m1::gather::gather_m1;
use abep_assess::closure_m1::{evaluate, M1Inputs, M1Outcome, NP_DIR};
use abep_mission::integration::Mode;
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::Value;
use abep_types::EvalStatus;
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

fn a4(o: &M1Outcome) -> &A4Outcome {
    o.a4.as_ref().unwrap()
}

fn verdict<'a>(o: &'a M1Outcome, id: &str) -> &'a Verdict {
    a4(o).verdicts.iter().find(|v| v.id == id).unwrap()
}

/// SYNTHETIC test-only area limit.
fn with_area(value_m2: f64, status: &str) -> M1Inputs {
    let mut inp = base().clone();
    inp.a4.as_mut().unwrap().area = AreaLimit::Registered {
        value_m2,
        status: status.into(),
        provenance: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
    };
    inp
}

fn a_req(o: &M1Outcome, k: usize) -> Vec<(String, f64)> {
    a4(o).states.iter().map(|s| (s.state_id.clone(), s.modes[&Mode::AirPrimary].a_req.unwrap()[k])).collect()
}

fn max_of(v: &[(String, f64)]) -> f64 {
    v.iter().map(|x| x.1).fold(f64::NEG_INFINITY, f64::max)
}

fn min_of(v: &[(String, f64)]) -> f64 {
    v.iter().map(|x| x.1).fold(f64::INFINITY, f64::min)
}

// ------------------------------------------------------------------------------------------------ today

#[test]
fn today_no_area_limit_is_registered_and_nothing_changes() {
    let inp = base();
    let o = base_out();
    let a = inp.a4.as_ref().unwrap();
    assert_eq!(a.area, AreaLimit::NotRegistered);
    assert_eq!(a.alt_band_km, (180.0, 230.0));
    assert_eq!(a.hc09_n, Some(0.025));
    let r = a4(o);
    assert_eq!(r.states.len(), 196);
    assert!(r.states.iter().all(|s| s.required && s.status == EvalStatus::Evaluated && s.codes.is_empty()));
    assert!(r.eligible_air_states.is_empty());
    for v in &r.verdicts {
        assert_eq!(v.status, BOUND_NOT_EVALUATED, "{}", v.id);
        assert!(!v.eligible);
    }
    assert!(verdict(o, "A4-T12-SUSTAINED").codes.contains(&A4_AREA_LIMIT_NOT_REGISTERED.to_string()));
    // the harness classification is the A2 dry-run result: C1, and no A4 code among the blockers
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C1"));
    assert!(o.outcome.blockers.iter().all(|(c, _)| !c.starts_with("A4_")));
    assert_eq!(ca4_cells(&o.states), 0);
    for (_, ms) in &o.states {
        for e in ms.values() {
            assert!(e.eval.constraints.iter().all(|c| c.id != A4_CONSTRAINT_ID));
        }
    }
}

#[test]
fn today_quantities_are_ordered_as_the_physics_requires() {
    let o = base_out();
    for s in &a4(o).states {
        let sp = s.speed.unwrap();
        let fl = s.flux.as_ref().unwrap();
        let am = &s.modes[&Mode::AirPrimary];
        assert!(sp.u_max_m_s >= sp.v_orb_max_m_s && sp.u_min_m_s < sp.u_max_m_s);
        assert!(fl.phi_max_kg_m2_s >= s.phi_adm.unwrap(), "Phi_max >= rho V");
        assert_eq!(am.p_avail_w, Some(1500.0), "P_nonHall,LB,eligible is 0 W today");
        let (ar, ar0, mr) = (am.a_req.unwrap(), am.a_req0.unwrap(), am.mdot_req.unwrap());
        assert!(ar[0] < ar[1] && mr[0] < mr[1]);
        assert!(ar[0] <= ar0[0] && ar[1] <= ar0[1], "energy inflow can only lower A_req");
        assert!(am.t_max_at_area.is_none());
        assert_eq!(am.t_max_grid.len(), F1_GRID_AREAS_M2.len());
        assert!(am.t_max_grid.windows(2).all(|w| w[0] < w[1]));
        let xe = &s.modes[&Mode::XeContingency];
        assert_eq!(xe.mdot_req, Some(mr));
        assert!(xe.a_req.is_none());
        assert!(xe.codes.contains(&XE_FEED_FLOW_NOT_REGISTERED_CODE.to_string()));
    }
}

const XE_FEED_FLOW_NOT_REGISTERED_CODE: &str = abep_assess::closure_m1::XE_FEED_FLOW_NOT_REGISTERED;

#[test]
fn v2_record_carries_the_a4_block_and_keeps_the_dry_run_classification() {
    let v = abep_assess::closure_m1::record::record_v2(base(), base_out(), "TEST");
    let blk = v.as_dict().unwrap().get("conservation_bounds_a4").unwrap();
    assert_eq!(blk, &record_block(base(), base_out()));
    let a = blk.as_dict().unwrap().get("addendum_a4").unwrap().as_dict().unwrap();
    assert_eq!(a.get("sha256").unwrap().as_str(), Some(A4_SHA256));
    let c = v.as_dict().unwrap().get("classification").unwrap().as_dict().unwrap();
    assert_eq!(c.get("procedure_step").unwrap().as_str(), Some("C1"));
}

// ------------------------------------------------------------------------------------------------ classification effect

#[test]
fn frozen_area_below_the_sustained_requirement_is_physically_non_closing_without_any_hall_envelope() {
    let t12 = a_req(base_out(), 0);
    let a_max = 0.5 * max_of(&t12);
    let inp = with_area(a_max, "FROZEN");
    assert!(inp.xe.is_none(), "no Hall envelope ingested");
    let o = evaluate(&inp).unwrap();
    let v = verdict(&o, "A4-T12-SUSTAINED");
    assert_eq!(v.status, BOUND_FAILS);
    assert!(v.eligible);
    let want: Vec<String> = t12.iter().filter(|(_, a)| *a > a_max).map(|(s, _)| s.clone()).collect();
    assert!(!want.is_empty() && want.len() < t12.len());
    assert_eq!(v.failing_states, want);
    let q = v.quantifier.as_dict().unwrap();
    assert_eq!(q.get("verdict").unwrap().as_str(), Some("FAIL"));
    // T25 capability: existence over the states; a state with A_req,25 <= A_max passes, so the bound holds
    assert!(min_of(&a_req(base_out(), 1)) < a_max);
    assert_eq!(verdict(&o, "A4-T25-CAPABILITY").status, BOUND_HOLDS);
    // CA4 precedes C1
    assert_eq!((o.outcome.classification, o.outcome.step), (PHYSICALLY_NON_CLOSING, "CA4"));
    assert_eq!(o.outcome.blockers, vec![(A4_CONSERVATION_BOUND_NON_CLOSING.to_string(), want.len())]);
    for (st, ms) in &o.states {
        let air = &ms[&Mode::AirPrimary];
        let has = air.eval.constraints.iter().any(|c| c.id == A4_CONSTRAINT_ID && c.eligible_non_close);
        assert_eq!(has, want.contains(&st.state_id));
        if has {
            assert_eq!(air.eval.status, PHYSICS_NON_CLOSING);
            assert_eq!(air.binding_constraint.as_deref(), Some(A4_CONSTRAINT_ID));
        }
        assert!(ms[&Mode::XeContingency].eval.constraints.iter().all(|c| c.id != A4_CONSTRAINT_ID), "XE never");
    }
    assert_eq!(
        abep_assess::closure_m1::category_a2(A4_CONSERVATION_BOUND_NON_CLOSING),
        "FUNDAMENTAL_ARCHITECTURE_LIMIT"
    );
}

#[test]
fn capability_fails_only_when_no_required_state_can_reach_25_mn() {
    let t25 = a_req(base_out(), 1);
    let o = evaluate(&with_area(0.5 * min_of(&t25), "FROZEN")).unwrap();
    let v = verdict(&o, "A4-T25-CAPABILITY");
    assert_eq!(v.status, BOUND_FAILS);
    assert!(v.eligible);
    assert_eq!(v.failing_states.len(), 196);
    assert_eq!(a4(&o).eligible_air_states.len(), 196);
    assert_eq!(o.outcome.step, "CA4");
    assert_eq!(o.outcome.blockers, vec![(A4_CONSERVATION_BOUND_NON_CLOSING.to_string(), 196)]);
}

#[test]
fn a_bound_that_holds_establishes_nothing() {
    let t12 = a_req(base_out(), 0);
    let o = evaluate(&with_area(2.0 * max_of(&a_req(base_out(), 1)).max(max_of(&t12)), "FROZEN")).unwrap();
    for id in ["A4-T12-SUSTAINED", "A4-T25-CAPABILITY"] {
        let v = verdict(&o, id);
        assert_eq!(v.status, BOUND_HOLDS);
        assert!(v.codes.contains(&A4_BOUND_HOLDS_NOTHING_ESTABLISHED.to_string()));
        assert!(!v.eligible);
    }
    assert_eq!(o.outcome.classification, base_out().outcome.classification);
    assert_eq!(o.outcome.step, base_out().outcome.step);
    assert_eq!(o.outcome.blockers, base_out().outcome.blockers);
    assert_eq!(o.outcome.evidence_conditions, base_out().outcome.evidence_conditions);
    for s in &a4(&o).states {
        assert!(s.modes[&Mode::AirPrimary].t_max_at_area.unwrap() >= 0.025);
    }
}

#[test]
fn a_provisional_area_limit_is_evaluated_but_never_eligible() {
    let o = evaluate(&with_area(0.01, "PROVISIONAL")).unwrap();
    for id in ["A4-T12-SUSTAINED", "A4-T25-CAPABILITY"] {
        let v = verdict(&o, id);
        assert_eq!(v.status, BOUND_FAILS);
        assert!(!v.eligible);
        assert!(v.codes.contains(&A4_AREA_LIMIT_NOT_FROZEN.to_string()));
    }
    assert!(a4(&o).eligible_air_states.is_empty());
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C1"));
    assert_eq!(o.outcome.blockers, base_out().outcome.blockers);
}

// ------------------------------------------------------------------------------------------------ fail closed

#[test]
fn a_state_without_wind_or_environment_is_not_evaluated_and_blocks_only_the_existence_claim() {
    let mut inp = with_area(0.001, "FROZEN");
    {
        let st = &mut inp.a4.as_mut().unwrap().states;
        st[0].wind_m_s = None;
        st[0].codes = vec![A4_WIND_NOT_AVAILABLE.into()];
        st[1].status = EvalStatus::OutOfDomain;
        st[1].codes = vec!["ENVIRONMENT_NOT_EVALUATED".into()];
    }
    let o = evaluate(&inp).unwrap();
    let r = a4(&o);
    assert_eq!(r.states[0].status, EvalStatus::NotEvaluated);
    assert!(r.states[0].codes.contains(&A4_WIND_NOT_AVAILABLE.to_string()));
    assert!(r.states[0].flux.is_none() && r.states[0].modes[&Mode::AirPrimary].a_req.is_none());
    assert_eq!(r.states[1].status, EvalStatus::NotEvaluated);
    // T12: the other 194 states fail on evaluated physics and are eligible; the two open states are not
    let v12 = verdict(&o, "A4-T12-SUSTAINED");
    assert_eq!((v12.status, v12.eligible, v12.failing_states.len()), (BOUND_FAILS, true, 194));
    assert!(!r.eligible_air_states.contains(&r.states[0].state_id));
    // T25: existence cannot be excluded while a state is open
    let v25 = verdict(&o, "A4-T25-CAPABILITY");
    assert_eq!((v25.status, v25.eligible), (BOUND_NOT_EVALUATED, false));
    assert_eq!(o.outcome.blockers, vec![(A4_CONSERVATION_BOUND_NON_CLOSING.to_string(), 194)]);
}

#[test]
fn out_of_domain_kernel_inputs_and_non_positive_power_are_not_evaluated() {
    let mut inp = with_area(0.001, "FROZEN");
    inp.a4.as_mut().unwrap().states[2].t_k = 0.0;
    let o = evaluate(&inp).unwrap();
    let s = &a4(&o).states[2];
    assert_eq!(s.status, EvalStatus::OutOfDomain);
    assert!(s.codes.iter().any(|c| c.starts_with(A4_INPUT_OUT_OF_DOMAIN)));
    assert!(!a4(&o).eligible_air_states.contains(&s.state_id));
    // P_avail <= 0: every bound NOT_EVALUATED (A2 NH-PBUS governs that case)
    let mut inp = with_area(0.001, "FROZEN");
    inp.today.limits.p_bus_max_w = 0.0;
    let o = evaluate(&inp).unwrap();
    for s in &a4(&o).states {
        assert!(s.modes[&Mode::AirPrimary].codes.contains(&A4_P_AVAIL_NOT_POSITIVE.to_string()));
        assert!(s.modes[&Mode::AirPrimary].a_req.is_none());
    }
    assert!(a4(&o).verdicts.iter().all(|v| !v.eligible));
}

#[test]
fn misaligned_state_lists_are_refused() {
    let mut inp = base().clone();
    inp.a4.as_mut().unwrap().states.swap(0, 1);
    assert_eq!(evaluate(&inp).unwrap_err().status(), EvalStatus::ModelError);
    let mut inp = base().clone();
    inp.a4.as_mut().unwrap().states.pop();
    assert_eq!(evaluate(&inp).unwrap_err().status(), EvalStatus::ModelError);
}

#[test]
fn without_a4_inputs_the_harness_is_unchanged() {
    let mut inp = base().clone();
    inp.a4 = None;
    let o = evaluate(&inp).unwrap();
    assert!(o.a4.is_none());
    assert_eq!(o.outcome.blockers, base_out().outcome.blockers);
    assert!(bounds_record(&inp, &o, "X").is_err());
}

fn scratch(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("abep_a4_{name}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn copy_into(tmp: &Path, rels: &[&str]) {
    for rel in rels {
        let dst = tmp.join(rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo().join(rel), dst).unwrap();
    }
}

#[test]
fn a4_pins_are_verified() {
    let files = [A4_REL, A4_MD_REL, A4_LOCK_REL];
    let t = scratch("pins");
    copy_into(&t, &files);
    verify_a4(&t).unwrap();
    for rel in files {
        let t2 = scratch("pinst");
        copy_into(&t2, &files);
        let p = t2.join(rel);
        let mut b = std::fs::read(&p).unwrap();
        let n = b.len();
        b[n / 2] ^= 1;
        std::fs::write(p, b).unwrap();
        assert_eq!(verify_a4(&t2).unwrap_err().status(), EvalStatus::ModelError, "{rel}");
        let _ = std::fs::remove_dir_all(&t2);
    }
    let _ = std::fs::remove_dir_all(&t);
}

#[test]
fn engineering_constraints_carry_no_area_limit_and_the_band() {
    let (band, area, hc09) = constraints(&repo()).unwrap();
    assert_eq!(band, (180.0, 230.0));
    assert_eq!(area, AreaLimit::NotRegistered);
    assert_eq!(hc09, Some(0.025));
}

// ------------------------------------------------------------------------------------------------ determinism, record

#[test]
fn record_is_deterministic() {
    let a = to_json(&bounds_record(base(), base_out(), "TEST").unwrap()).unwrap();
    let o2 = evaluate(base()).unwrap();
    let b = to_json(&bounds_record(base(), &o2, "TEST").unwrap()).unwrap();
    assert_eq!(a, b);
    let syn = with_area(0.1, "FROZEN");
    let x = to_json(&bounds_record(&syn, &evaluate(&syn).unwrap(), "TEST").unwrap()).unwrap();
    let y = to_json(&bounds_record(&syn, &evaluate(&syn).unwrap(), "TEST").unwrap()).unwrap();
    assert_eq!(x, y);
}

#[test]
fn committed_record_is_the_a4_record_of_today() {
    let rel = format!("{NP_DIR}/conservation_bounds_v1.json");
    let text = std::fs::read_to_string(repo().join(&rel)).unwrap();
    let v = abep_types::pyjson::loads(&text).unwrap();
    let d = v.as_dict().unwrap();
    assert_eq!(d.get("schema").unwrap().as_str(), Some(RECORD_SCHEMA));
    assert_eq!(d.get("run_label").unwrap().as_str(), Some("A4_CONSERVATION_BOUNDS_V1"));
    let commit = d.get("rust_commit").and_then(Value::as_str).unwrap().to_string();
    let mut inp = base().clone();
    inp.today.mission.provenance.rust_commit = commit;
    let out = evaluate(&inp).unwrap();
    let now = to_json(&bounds_record(&inp, &out, "A4_CONSERVATION_BOUNDS_V1").unwrap()).unwrap();
    assert_eq!(now, text, "byte-identical regeneration");
    assert!(!text.contains("SYNTHETIC"));
}
