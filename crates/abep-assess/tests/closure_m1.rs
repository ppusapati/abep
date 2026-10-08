//! NP-HALL-PARAMETRIC-ENVELOPE addendum A2: harness v2 (every required physics path of the M1 exit item), the M1
//! readiness listing, the classification branches on SYNTHETIC test-only inputs, fail-closed behaviour of every path and
//! determinism. Every synthetic value carries SYNTHETIC_TEST_DATA_NOT_EVIDENCE semantics and never enters a record.

use abep_assess::closure::{
    to_json, Constraint, CLOSES, CLOSES_IN_ENVELOPE, NON_CLOSING, NOT_DETERMINABLE, NOT_DETERMINABLE_IN_ENVELOPE,
    NOT_EVALUATED, OPEN, PHYSICALLY_NON_CLOSING, PHYSICS_FEASIBLE, PHYSICS_NON_CLOSING,
    SELECT_WITH_EVIDENCE_CONDITIONS,
};
use abep_assess::closure_m1::gather::{a1_on_line, gather_m1, icp_mode, verify_a2};
use abep_assess::closure_m1::record::{readiness, record_v2, Readiness};
use abep_assess::closure_m1::*;
use abep_hall::envelope::{self as env, CaseInfo, Envelope, EnvelopePoint, Family, RunStatus};
use abep_mission::integration::Mode;
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

/// Today's production inputs (gathered once).
fn base() -> &'static M1Inputs {
    static B: OnceLock<M1Inputs> = OnceLock::new();
    B.get_or_init(|| gather_m1(&repo(), None, None, "test").unwrap())
}

fn base_out() -> &'static M1Outcome {
    static O: OnceLock<M1Outcome> = OnceLock::new();
    O.get_or_init(|| evaluate(base()).unwrap())
}

fn today_record() -> &'static Value {
    static R: OnceLock<Value> = OnceLock::new();
    R.get_or_init(|| record_v2(base(), base_out(), "TEST"))
}

fn at<'a>(v: &'a Value, path: &[&str]) -> &'a Value {
    path.iter().fold(v, |x, k| x.as_dict().unwrap_or_else(|| panic!("{k}")).get(k).unwrap_or_else(|| panic!("{k}")))
}

fn st(v: &Value) -> &str {
    v.as_str().unwrap()
}

fn blocker_codes(o: &M1Outcome) -> BTreeSet<String> {
    o.outcome.blockers.iter().map(|(c, _)| c.clone()).collect()
}

fn constraint<'a>(o: &'a M1Outcome, m: Mode, id: &str) -> Vec<&'a Constraint> {
    o.states
        .iter()
        .filter(|(s, _)| s.required)
        .map(|(_, ms)| ms[&m].eval.constraints.iter().find(|c| c.id == id).unwrap())
        .collect()
}

// ------------------------------------------------------------------------------------------------ today (dry run)

#[test]
fn today_is_c1_not_determinable_with_every_registered_open_path() {
    let o = base_out();
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C1"));
    let codes = blocker_codes(o);
    for c in [
        abep_assess::closure::HALL_ENVELOPE_NOT_RUN,
        abep_assess::closure::AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED,
        GAS_PATH_ROBUST_SET_EMPTY,
        XE_FEED_FLOW_NOT_REGISTERED,
        ICP_CAPACITY_NOT_EVALUATED,
        abep_assess::closure::BUS_LEDGER_NOT_COMPLETE,
        "HOST_SPACECRAFT_DRAG_ICD_ABSENT",
        abep_assess::closure::MASS_INCOMPLETE_EVIDENCE,
        THERMAL_LOADS_NOT_EVALUATED,
        THERMAL_FLIGHT_CASE_NOT_REGISTERED,
        abep_assess::closure::LIFE_NOT_EVALUATED,
    ] {
        assert!(codes.contains(c), "{c} missing from {codes:?}");
    }
    assert_eq!(o.states.len(), 196);
    for (s, ms) in &o.states {
        for m in [Mode::AirPrimary, Mode::XeContingency] {
            assert_eq!(ms[&m].eval.status, NOT_DETERMINABLE, "{}", s.state_id);
            assert_eq!(ms[&m].bus.lb_w, 0.0, "P_nonHall,LB equals the v1 value today");
        }
    }
    // No layer (a) constraint is eligible either way today; the planning mass never supports a non-closure.
    for m in [Mode::AirPrimary, Mode::XeContingency] {
        for id in ["NH-FLOW", "NH-ICP", "NH-PBUS", "NH-MASS", "NH-THERMAL", "NH-LIFE"] {
            assert!(constraint(o, m, id)
                .iter()
                .all(|c| c.status == OPEN && !c.eligible_close && !c.eligible_non_close));
        }
    }
    assert!(constraint(o, Mode::AirPrimary, "NH-FLOW").iter().all(|c| c.codes == [GAS_PATH_ROBUST_SET_EMPTY]));
    assert!(constraint(o, Mode::XeContingency, "NH-FLOW").iter().all(|c| c.codes == [XE_FEED_FLOW_NOT_REGISTERED]));
    assert!(constraint(o, Mode::AirPrimary, "NH-TD").iter().all(|c| c.codes == ["HOST_SPACECRAFT_DRAG_ICD_ABSENT"]));
}

#[test]
fn today_record_carries_layers_findings_and_the_f8_result_unchanged() {
    let r = today_record();
    assert_eq!(st(at(r, &["schema"])), SCHEMA);
    assert_eq!(st(at(r, &["addendum_a2", "sha256"])), A2_SHA256);
    assert_eq!(st(at(r, &["inputs", "credible_set"])), "EMPTY");
    assert_eq!(at(r, &["inputs", "n_required_states"]), &Value::int(196));
    let f = &at(r, &["binding_findings"]).as_list().unwrap()[0];
    assert_eq!(st(at(f, &["id"])), GAS_PATH_ROBUST_SET_EMPTY);
    assert_eq!(st(at(f, &["category"])), "DESIGN_VARIABLE_LIMIT");
    assert_eq!(at(f, &["n_required_states_bound"]), &Value::int(196));
    let dec = at(f, &["f8_decomposition"]);
    assert_eq!(st(at(dec, &["robust_set"])), "EMPTY");
    assert_eq!(at(dec, &["n_survivors"]), &Value::int(90));
    assert_eq!(at(dec, &["infeasibility_reason_counts", "TARGET_AT_OR_ABOVE_DEAD_HEAD_PRESSURE"]), &Value::int(452));
    assert_eq!(at(dec, &["infeasibility_reason_counts", "GAEDE_CHARACTERISTIC_OUTSIDE_K_1_TO_K0"]), &Value::int(273));
    // The F7 frontier is reported raw against the Hall grid floor.
    let p = at(r, &["paths", "P-FLOW"]);
    assert_eq!(at(p, &["hall_envelope_grid_floor_kg_s"]), &Value::Float(3.77e-7));
    let fr = at(p, &["frontier_overall", "mdot_delivered_min_kgps"]).to_f64().unwrap();
    assert!(fr > 0.0 && fr < 3.77e-7);
    assert_eq!(st(at(p, &["f8", "verdict"])), "PARITY_PASS");
    assert_eq!(st(at(p, &["plenum_feed", "verdict_v8"])), "PARITY_FAIL");
    // Layer (b) unchanged, CPL and HC-05 NOT_EVALUATED.
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
        assert_eq!(at(r, &["layer_b", "n_states_evidence_qualified_b", m]), &Value::int(0));
        assert_eq!(st(at(r, &["paths", "P-CPL", m, "cpl_hall_on_v1", "status"])), NOT_EVALUATED);
        assert_eq!(st(at(r, &["paths", "P-CPL", m, "hc05_layer_b", "status"])), NOT_EVALUATED);
    }
    for s in at(r, &["states"]).as_list().unwrap() {
        for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
            let fl = at(s, &["modes", m, "layer_a", "fields"]);
            assert_eq!(st(at(fl, &["P_nonHall_LB_W", "status"])), "LOWER_BOUND");
            assert_eq!(st(at(fl, &["I_e_cap_fav_A", "status"])), NOT_EVALUATED);
            assert_eq!(st(at(s, &["modes", m, "layer_b", "status"])), NOT_EVALUATED);
        }
    }
    // Every per-state field is described by the catalog (layer, producer path, binding attribution).
    let cat = at(r, &["field_catalog", "fields"]).as_dict().unwrap();
    for s in at(r, &["states"]).as_list().unwrap().iter().take(3) {
        for (k, _) in at(s, &["modes", "AIR_PRIMARY", "layer_a", "fields"]).as_dict().unwrap().iter() {
            assert!(cat.contains_key(k), "{k} not in the field catalog");
        }
    }
}

#[test]
fn readiness_lists_every_registered_path_and_none_is_blocked() {
    let a2: serde_json::Value = serde_json::from_slice(&std::fs::read(repo().join(A2_REL)).unwrap()).unwrap();
    let want: Vec<String> =
        a2["readiness"]["required_paths"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect();
    let r = readiness(base());
    let got: Vec<String> = r.iter().map(|x| x.id.to_string()).collect();
    assert_eq!(got, want);
    assert!(r.iter().all(|x| x.status != Readiness::Blocked));
    let by: BTreeMap<&str, &abep_assess::closure_m1::record::PathReadiness> = r.iter().map(|x| (x.id, x)).collect();
    assert_eq!(by["P-HALL-XE"].status, Readiness::AwaitingInput);
    assert_eq!(by["P-HALL-XE"].codes, ["HALL_ENVELOPE_NOT_RUN"]);
    assert_eq!(by["P-HALL-AIR"].status, Readiness::AwaitingInput);
    assert_eq!(by["P-THERMAL"].status, Readiness::AwaitingInput);
    for id in ["P-ENV", "P-FLOW", "P-ICP", "P-CPL", "P-PBUS", "P-MASS", "P-LIFE", "P-TD", "P-LAYER-B"] {
        assert_eq!(by[id].status, Readiness::Consumed, "{id}");
    }
    assert_eq!(at(today_record(), &["readiness", "m1_exit_item_harness_consumes_all_paths"]), &Value::Bool(true));
}

#[test]
fn harness_v2_is_deterministic() {
    let a = to_json(&record_v2(base(), &evaluate(base()).unwrap(), "DET")).unwrap();
    let b = to_json(&record_v2(base(), &evaluate(base()).unwrap(), "DET")).unwrap();
    assert_eq!(a, b);
    let again = gather_m1(&repo(), None, None, "test").unwrap();
    let c = to_json(&record_v2(&again, &evaluate(&again).unwrap(), "DET")).unwrap();
    assert_eq!(a, c);
}

// ------------------------------------------------------------------------------------------------ synthetic inputs

fn ci(fam: Family, key: &str, geom: &str, tr: &str, mdot: f64) -> CaseInfo {
    CaseInfo {
        key: format!("{SYNTHETIC}|{key}"),
        family: fam,
        geometry_id: geom.into(),
        bz_shape_id: "BZ-SYN".into(),
        b_peak_id: "BP".into(),
        vd_id: "VD".into(),
        mdot_id: "MF".into(),
        transport_id: tr.into(),
        vd_v: 300.0,
        mdot_kg_s: mdot,
        b_peak_t: 0.02,
        case_sha256: SYNTHETIC.into(),
    }
}

fn pt(case: CaseInfo, status: RunStatus, t: f64, pd: f64, id: f64) -> EnvelopePoint {
    let pass = status == RunStatus::Pass;
    EnvelopePoint {
        case,
        status,
        thrust_n: pass.then_some(t),
        discharge_power_w: pass.then_some(pd),
        discharge_current_a: pass.then_some(id),
        ion_current_a: pass.then_some(0.8 * id),
        te_max_ev: None,
    }
}

/// A synthetic XE envelope on two hardware configurations: G1 (I_d 3 A) and G2 (I_d 1 A), both PASS at 10 mN / 900 W.
fn xe_envelope(bz: env::BzFamilyKind) -> Envelope {
    Envelope {
        manifest_rel: SYNTHETIC.into(),
        manifest_sha256: SYNTHETIC.into(),
        raw_sha256: SYNTHETIC.into(),
        cases_sha256: SYNTHETIC.into(),
        bz_family_kind: bz,
        points: vec![
            pt(ci(Family::Xe, "XE|G1", "G1", "sgb-a", 1e-6), RunStatus::Pass, 0.010, 900.0, 3.0),
            pt(ci(Family::Xe, "XE|G2", "G2", "sgb-a", 3e-6), RunStatus::Pass, 0.010, 900.0, 1.0),
            pt(ci(Family::Xe, "XE|G3", "G3", "sgb-a", 3e-6), RunStatus::NotSustained, 0.0, 0.0, 0.0),
        ],
    }
}

const CORNERS: [&str; 4] = ["CP-YLO-REC", "CP-YLO-DIS", "CP-YHI-REC", "CP-YHI-DIS"];

/// A synthetic AIR family: G1 (mdot 1 mg/s, I_d 3 A) and G2 (mdot 3 mg/s, I_d 1 A) close T12 and T25 at every corner.
fn air(points_at: &[(&str, f64, f64, f64)]) -> AirHallInput {
    let mut points = vec![];
    for c in CORNERS {
        for (g, mdot, t, id) in points_at {
            points.push(AirPoint {
                composition_id: c.into(),
                point: pt(
                    ci(Family::N2Proxy, &format!("AIR|{g}|{c}"), g, "sgb-a", *mdot),
                    RunStatus::Pass,
                    *t,
                    1000.0,
                    *id,
                ),
            });
        }
    }
    AirHallInput {
        points,
        corners: CORNERS.iter().map(|c| c.to_string()).collect(),
        state_exclusions: BTreeMap::new(),
        bz_family_kind: env::BzFamilyKind::SourcedSurrogate,
        bounded: false,
        provenance: SYNTHETIC.into(),
    }
}

fn with_air(inp: &mut M1Inputs, a: AirHallInput) {
    inp.a1_on_line = true;
    inp.air = AirHall::Ingested(a);
}

fn with_icp(inp: &mut M1Inputs, ie: f64) {
    for m in inp.icp.modes.values_mut() {
        m.i_e_cap_fav_a = Some(ie);
        m.member_id = Some(SYNTHETIC.into());
    }
}

fn with_flow(inp: &mut M1Inputs, mdot: f64, p_comp: Option<f64>, feed: FeedLoop) {
    inp.flow.robust_members = vec![SYNTHETIC.into()];
    let mut per = BTreeMap::new();
    for s in &inp.today.states {
        let mut m = BTreeMap::new();
        m.insert(SYNTHETIC.to_string(), MemberState { mdot_kg_s: mdot, x_o: Some(0.4), p_compressor_w: p_comp, feed });
        per.insert(s.state_id.clone(), m);
    }
    inp.flow.per_state = Some(per);
}

/// Every A2 path closing that A2 lets close: thermal, mass and life evaluated inside their limits.
fn with_closing_subsystems(inp: &mut M1Inputs) {
    let mut th = BTreeMap::new();
    for s in &inp.today.states {
        for m in [Mode::AirPrimary, Mode::XeContingency] {
            th.insert(
                (s.state_id.clone(), m),
                ThermalState { converged: true, margin_k: Some(120.0), t_max_k: Some(500.0), codes: vec![] },
            );
        }
    }
    inp.thermal.per_state = Some(th);
    inp.mass.cbe_wet_kg = Some(39.0);
    inp.life.firing_life_h = Some(20_000.0);
    inp.hc07_h = inp.hc07_h.or(Some(15_000.0));
}

fn synthetic_chain() -> M1Inputs {
    let mut inp = base().clone();
    // The A2 path tests run the A2 + A4 harness; addendum A5 (intake closure) has its own tests.
    inp.a5 = None;
    inp.xe = Some(xe_envelope(env::BzFamilyKind::SourcedSurrogate));
    with_air(&mut inp, air(&[("G1", 1e-6, 0.030, 3.0), ("G2", 3e-6, 0.030, 1.0)]));
    with_icp(&mut inp, 5.0);
    with_flow(&mut inp, 4e-6, Some(10.0), FeedLoop::Stable);
    with_closing_subsystems(&mut inp);
    inp
}

#[test]
fn synthetic_full_chain_leaves_only_the_a2_registered_open_conditions() {
    let inp = synthetic_chain();
    let o = evaluate(&inp).unwrap();
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C4"));
    let codes = blocker_codes(&o);
    let want: BTreeSet<String> =
        [abep_assess::closure::BUS_LEDGER_NOT_COMPLETE, "HOST_SPACECRAFT_DRAG_ICD_ABSENT", XE_FEED_FLOW_NOT_REGISTERED]
            .iter()
            .map(|x| x.to_string())
            .collect();
    assert_eq!(codes, want, "only the conditions A2 cannot close remain");
    for id in ["HALL_T12_AT_PBUS", "HALL_T25_CAPABILITY", "NH-FLOW", "NH-ICP", "NH-MASS", "NH-THERMAL", "NH-LIFE"] {
        assert!(constraint(&o, Mode::AirPrimary, id).iter().all(|c| c.eligible_close), "{id}");
    }
    let air_t12 = constraint(&o, Mode::AirPrimary, "HALL_T12_AT_PBUS")[0];
    assert!(air_t12.evidence_conditions.iter().any(|e| e.starts_with("EC-COMP")));
    assert!(air_t12.evidence_conditions.iter().any(|e| e.starts_with("EC-BZ")));
    for (_, ms) in &o.states {
        assert_eq!(ms[&Mode::AirPrimary].joint_hardware.len(), 2);
        assert_eq!(ms[&Mode::AirPrimary].delivered, Some((4e-6, Some(0.4))));
        // The compressor draw of the robust member enters P_nonHall,LB (favorable: TBD efficiency -> 1).
        assert_eq!(ms[&Mode::AirPrimary].bus.lb_w, 10.0);
        assert_eq!(ms[&Mode::XeContingency].bus.lb_w, 0.0);
    }
    // Record: CPL at a parametric point (smallest joint I_d), outputs still NOT_EVALUATED; M_n as a model quantity.
    let r = record_v2(&inp, &o, "TEST");
    let c = at(&r, &["paths", "P-CPL", "XE_CONTINGENCY"]);
    assert!(st(at(c, &["hall_point"])).contains("XE|G2"));
    // Gated: HI-07 not registered makes it INCOMPLETE_EVIDENCE; every output NOT_EVALUATED.
    assert_eq!(st(at(c, &["cpl_hall_on_v1", "status"])), "INCOMPLETE_EVIDENCE");
    let outs = at(c, &["cpl_hall_on_v1", "outputs"]).as_dict().unwrap();
    assert!(outs.iter().all(|(_, v)| st(v) == NOT_EVALUATED));
    assert_eq!(at(c, &["cpl_hall_on_v1", "inputs", "HI-01_I_d_A", "value"]), &Value::Float(1.0));
    assert_eq!(at(c, &["neutralization_quantities_layer_a", "M_n_point"]), &Value::Float(4.0));
    assert_eq!(st(at(c, &["hc05_layer_b", "status"])), NOT_EVALUATED);
    let s0 = &at(&r, &["states"]).as_list().unwrap()[0];
    assert_eq!(
        at(s0, &["modes", "AIR_PRIMARY", "layer_a", "fields", "thrust_joint_max_N", "value"]),
        &Value::Float(0.030)
    );
    assert_eq!(
        at(s0, &["modes", "AIR_PRIMARY", "layer_a", "fields", "mdot_atm_delivered_kg_s", "value"]),
        &Value::Float(4e-6)
    );
    assert_eq!(at(&r, &["layer_b", "n_states_evidence_qualified_b", "AIR_PRIMARY"]), &Value::int(0));
}

/// Replace the constraints A2 can never close (NH-PBUS without a complete ledger, NH-TD, XE NH-FLOW) by SYNTHETIC
/// closures and re-run the per-state rule and the procedure: the C3 / joint branches of the classification.
fn substituted(inp: &M1Inputs, o: &M1Outcome) -> abep_assess::closure::ClosureOutcome {
    let mut states = o.states.clone();
    for (_, ms) in &mut states {
        for (m, e) in ms.iter_mut() {
            let nh: Vec<Constraint> = e
                .eval
                .constraints
                .iter()
                .filter(|c| !c.hall_specific)
                .map(|c| {
                    if c.id == "NH-PBUS" || c.id == "NH-TD" || (*m == Mode::XeContingency && c.id == "NH-FLOW") {
                        Constraint {
                            id: c.id.clone(),
                            hall_specific: false,
                            status: CLOSES,
                            eligible_close: true,
                            eligible_non_close: false,
                            codes: vec![],
                            detail: SYNTHETIC.into(),
                            evidence_conditions: vec![format!("EC-{} ({SYNTHETIC})", c.id)],
                        }
                    } else {
                        c.clone()
                    }
                })
                .collect();
            e.eval = finalize_mode(&e.hall, &nh, &e.joint_hardware);
        }
    }
    classify_v2(inp.today.credible_set_empty, inp.xe.is_some(), &states)
}

#[test]
fn synthetic_c3_select_with_evidence_conditions_after_substitution() {
    let inp = synthetic_chain();
    let out = substituted(&inp, &evaluate(&inp).unwrap());
    assert_eq!((out.classification, out.step), (SELECT_WITH_EVIDENCE_CONDITIONS, "C3"));
    assert!(out.common_hardware.contains(&("G1".to_string(), "BZ-SYN".to_string())));
    for ec in [
        "EC-TRANSPORT",
        "EC-BZ",
        "EC-COMP",
        "EC-CHEM",
        "EC-INLET",
        "EC-FLOW",
        "EC-ICP",
        "EC-THERMAL",
        "EC-MASS",
        "EC-LIFE",
    ] {
        assert!(out.evidence_conditions.iter().any(|e| e.starts_with(ec)), "{ec} missing");
    }
    assert!(out.states.iter().all(|(_, m)| m.values().all(|e| e.status == PHYSICS_FEASIBLE)));
}

#[test]
fn synthetic_joint_point_conditions_on_disjoint_hardware_are_not_determinable() {
    // Flow reaches only G1 (mdot 1 mg/s <= 2 mg/s); I_e,cap covers only G2 (I_d 1 A <= 2 A): each constraint closes
    // on its own, no hardware has a joint point.
    let mut inp = synthetic_chain();
    with_icp(&mut inp, 2.0);
    with_flow(&mut inp, 2e-6, Some(10.0), FeedLoop::Stable);
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::AirPrimary, "NH-FLOW").iter().all(|c| c.eligible_close));
    assert!(constraint(&o, Mode::AirPrimary, "NH-ICP").iter().all(|c| c.eligible_close));
    assert!(o.states.iter().all(|(_, m)| m[&Mode::AirPrimary].joint_hardware.is_empty()));
    let out = substituted(&inp, &o);
    assert_eq!(out.classification, NOT_DETERMINABLE);
    assert_eq!(out.blockers, vec![(JOINT_CLOSING_POINT_ABSENT.to_string(), 196)]);
    assert_eq!(category_a2(JOINT_CLOSING_POINT_ABSENT), "DESIGN_VARIABLE_LIMIT");
}

#[test]
fn synthetic_c2_from_an_eligible_bus_lower_bound() {
    // An admitted-producer compressor draw >= 1500 W alone is an evaluated lower bound: PHYSICALLY_NON_CLOSING.
    let mut inp = synthetic_chain();
    with_flow(&mut inp, 4e-6, Some(1600.0), FeedLoop::Stable);
    let o = evaluate(&inp).unwrap();
    assert_eq!((o.outcome.classification, o.outcome.step), (PHYSICALLY_NON_CLOSING, "C2"));
    assert!(constraint(&o, Mode::AirPrimary, "NH-PBUS").iter().all(|c| c.eligible_non_close));
    assert!(o.states.iter().all(|(_, m)| m[&Mode::AirPrimary].eval.status == PHYSICS_NON_CLOSING));
    // The same draw from an unverified producer never supports a non-closure.
    inp.flow.compressor_eligible = false;
    let o = evaluate(&inp).unwrap();
    assert_eq!(o.outcome.classification, NOT_DETERMINABLE);
    assert!(constraint(&o, Mode::AirPrimary, "NH-PBUS").iter().all(|c| !c.eligible_non_close));
}

#[test]
fn synthetic_c2_from_an_evaluated_mass_lower_bound_and_never_from_planning() {
    let mut inp = synthetic_chain();
    inp.mass.cbe_lower_bound_kg = Some(41.0);
    let o = evaluate(&inp).unwrap();
    assert_eq!((o.outcome.classification, o.outcome.step), (PHYSICALLY_NON_CLOSING, "C2"));
    assert_eq!(category_a2(MASS_CBE_LOWER_BOUND_AT_LIMIT), "FUNDAMENTAL_ARCHITECTURE_LIMIT");
    // A point estimate above the limit is not a lower bound: not eligible.
    let mut inp = synthetic_chain();
    inp.mass.cbe_wet_kg = Some(41.0);
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::AirPrimary, "NH-MASS")
        .iter()
        .all(|c| c.status == NON_CLOSING && !c.eligible_non_close));
    assert_eq!(o.outcome.classification, NOT_DETERMINABLE);
}

#[test]
fn synthetic_c0_and_c1() {
    let mut inp = synthetic_chain();
    inp.today.credible_set_empty = false;
    assert_eq!(evaluate(&inp).unwrap().outcome.step, "C0");
    let mut inp = synthetic_chain();
    inp.xe = None;
    let o = evaluate(&inp).unwrap();
    assert_eq!((o.outcome.classification, o.outcome.step), (NOT_DETERMINABLE, "C1"));
}

#[test]
fn synthetic_surrogate_xe_non_closure_is_never_physically_non_closing() {
    let mut inp = synthetic_chain();
    let mut e = xe_envelope(env::BzFamilyKind::SourcedSurrogate);
    for p in &mut e.points {
        if p.status == RunStatus::Pass {
            p.thrust_n = Some(0.0);
        }
    }
    inp.xe = Some(e.clone());
    let o = evaluate(&inp).unwrap();
    assert_eq!(o.outcome.classification, NOT_DETERMINABLE);
    assert!(blocker_codes(&o).contains(abep_assess::closure::H1_BZ_NOT_REGISTERED));
    e.bz_family_kind = env::BzFamilyKind::H1Registered;
    inp.xe = Some(e);
    assert_eq!(evaluate(&inp).unwrap().outcome.classification, PHYSICALLY_NON_CLOSING);
}

// ------------------------------------------------------------------------------------------------ fail closed per path

#[test]
fn p_flow_unstable_feed_loop_is_a_finding_and_never_a_held_number() {
    let mut inp = synthetic_chain();
    with_flow(&mut inp, 4e-6, Some(10.0), FeedLoop::UnstableEquilibrium { re_lambda_max: 2.4e-3 });
    let o = evaluate(&inp).unwrap();
    for c in constraint(&o, Mode::AirPrimary, "NH-FLOW") {
        assert_eq!((c.status, c.eligible_non_close), (NON_CLOSING, false));
        assert_eq!(c.codes, [FEED_LOOP_UNSTABLE_EQUILIBRIUM]);
    }
    assert!(o.states.iter().all(|(_, m)| m[&Mode::AirPrimary].delivered.is_none()));
    with_flow(&mut inp, 4e-6, Some(10.0), FeedLoop::ControllerNotRegistered);
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::AirPrimary, "NH-FLOW")
        .iter()
        .all(|c| c.status == OPEN && c.codes == [FEED_CONTROLLER_NOT_REGISTERED]));
    // Robust members without per-state chain values.
    inp.flow.per_state = None;
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::AirPrimary, "NH-FLOW")
        .iter()
        .all(|c| c.codes == [GASPATH_PER_STATE_VALUES_NOT_SUPPLIED]));
}

#[test]
fn p_flow_below_every_closing_mdot_is_not_eligible() {
    let mut inp = synthetic_chain();
    with_flow(&mut inp, 1e-8, Some(10.0), FeedLoop::Stable);
    let o = evaluate(&inp).unwrap();
    for c in constraint(&o, Mode::AirPrimary, "NH-FLOW") {
        assert_eq!((c.status, c.eligible_non_close), (NON_CLOSING, false));
        assert_eq!(c.codes, [GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT]);
    }
    assert_eq!(category_a2(GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT), "DESIGN_VARIABLE_LIMIT");
}

#[test]
fn p_icp_below_every_closing_i_d_is_not_eligible_and_absent_capacity_is_open() {
    let mut inp = synthetic_chain();
    with_icp(&mut inp, 0.5);
    let o = evaluate(&inp).unwrap();
    for m in [Mode::AirPrimary, Mode::XeContingency] {
        assert!(constraint(&o, m, "NH-ICP")
            .iter()
            .all(|c| c.status == NON_CLOSING && !c.eligible_non_close && c.codes == [ICP_CAPACITY_BELOW_HALL_I_D]));
    }
    let o = evaluate(&{
        let mut x = synthetic_chain();
        x.icp = base().icp.clone();
        x
    })
    .unwrap();
    assert!(constraint(&o, Mode::XeContingency, "NH-ICP")
        .iter()
        .all(|c| c.codes.contains(&ICP_CAPACITY_NOT_EVALUATED.to_string())));
}

#[test]
fn p_icp_consumes_a_converged_v2_result_and_refuses_a_bad_bus_record() {
    use abep_icp::v2::testkit::capoff_case_v2;
    let m = abep_icp::v2::IcpModelV2::load(&repo()).unwrap();
    let r = m.evaluate(&capoff_case_v2(30.0, 0.0, 30.0));
    let im = icp_mode(&r).unwrap();
    let env_max = r.if_icp_hall_v1.i_e_cap_envelope_a["max"].clone();
    assert_eq!(im.i_e_cap_fav_a, env_max.value.filter(|_| env_max.status.is_converged()));
    assert!(im.i_e_cap_fav_a.is_some_and(|x| x > 0.0), "the synthetic CAP-OFF case converges");
    // A retired key in the IF-ICP-BUS-v2 record of the chosen member refuses the whole record.
    {
        let mid = im.member_id.clone().unwrap();
        let mut bad = r.clone();
        let rec = bad.if_icp_bus_v2.iter_mut().find(|b| b.solve_member_id == mid).unwrap();
        let k = rec.keys.keys().next().unwrap().clone();
        let mut q = rec.keys[&k].clone();
        q.id = "BK-XX".into();
        rec.keys.insert("P_icp_bus_W".into(), q);
        assert!(icp_mode(&bad).is_err());
    }
    // A MODEL_ERROR result refuses the record.
    let mut bad = r.clone();
    bad.status = abep_icp::IcpStatus::ModelError;
    assert!(icp_mode(&bad).is_err());
}

#[test]
fn p_pbus_refuses_overrides_of_the_reserved_port_and_lists_every_tbd_term() {
    use abep_subsystems::power::slots::Slot;
    let b = non_hall_bus(&base().mp, &[]).unwrap();
    assert_eq!((b.lb_w, b.lb_eligible_w, b.p_nonhall_w), (0.0, 0.0, None));
    assert!(b.tbd.iter().any(|t| t.0 == "compressor" && t.1 == "load"));
    assert!(!b.tbd.iter().any(|t| t.0 == "hall_discharge" && t.1 == "load"));
    assert!(non_hall_bus(&base().mp, &[(Slot::ReservedDcPort, 1.0, "x".into(), true)]).is_err());
    let b = non_hall_bus(
        &base().mp,
        &[(Slot::IcpRfSource, 40.0, "x".into(), false), (Slot::Compressor, 9.0, "y".into(), true)],
    )
    .unwrap();
    assert_eq!((b.lb_w, b.lb_eligible_w), (49.0, 9.0));
}

#[test]
fn p_air_composition_rule_species_bounds_and_common_hardware() {
    // A missing corner on every hardware: no closure, never eligible.
    let mut inp = synthetic_chain();
    let mut a = air(&[("G1", 1e-6, 0.030, 3.0)]);
    a.points.retain(|p| p.composition_id != "CP-YHI-DIS");
    with_air(&mut inp, a);
    let o = evaluate(&inp).unwrap();
    for c in constraint(&o, Mode::AirPrimary, "HALL_T12_AT_PBUS") {
        assert_eq!(c.status, NOT_DETERMINABLE_IN_ENVELOPE);
        assert!(c.codes.contains(&HALL_NON_CLOSING_UNDER_AIR_ENVELOPE.to_string()));
        assert!(!c.eligible_non_close);
    }
    // T12 closes on G1 (13 mN at every corner); T25 only where 25 mN is reached at every corner (G2).
    let mut inp = synthetic_chain();
    with_air(&mut inp, air(&[("G1", 1e-6, 0.013, 3.0), ("G2", 3e-6, 0.026, 1.0)]));
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::AirPrimary, "HALL_T25_CAPABILITY").iter().all(|c| c.status == CLOSES_IN_ENVELOPE));
    let hw: Vec<(String, String)> = o.states[0].1[&Mode::AirPrimary].joint_hardware.iter().cloned().collect();
    assert_eq!(hw, vec![("G2".to_string(), "BZ-SYN".to_string())], "T12 and T25 on one hardware");
    // State exclusions (A1 SB-He): AIR Hall NOT_EVALUATED at that state only.
    let mut inp = synthetic_chain();
    let mut a = air(&[("G1", 1e-6, 0.030, 3.0)]);
    let sid = inp.today.states[0].state_id.clone();
    a.state_exclusions.insert(sid.clone(), MATERIALITY_BOUND_REQUIRED_HE.into());
    with_air(&mut inp, a);
    let o = evaluate(&inp).unwrap();
    let e = &o.states[0].1[&Mode::AirPrimary];
    assert_eq!(o.states[0].0.state_id, sid);
    assert!(e
        .hall
        .iter()
        .all(|h| h.constraint.status == NOT_EVALUATED && h.constraint.codes == [MATERIALITY_BOUND_REQUIRED_HE]));
    assert!(o.states[1].1[&Mode::AirPrimary].hall.iter().all(|h| h.constraint.eligible_close));
    assert_eq!(category_a2(MATERIALITY_BOUND_REQUIRED_HE), "MODEL_DOMAIN_LIMIT");
}

#[test]
fn p_env_a_state_without_evaluated_environment_is_open() {
    let mut inp = synthetic_chain();
    let sid = inp.today.states[0].state_id.clone();
    inp.today.mission.states.iter_mut().find(|s| s.state_id == sid).unwrap().environment_status =
        abep_types::EvalStatus::OutOfDomain;
    let o = evaluate(&inp).unwrap();
    let e = &o.states[0].1[&Mode::XeContingency];
    assert!(e.eval.constraints.iter().filter(|c| !c.hall_specific).all(|c| c.codes == [ENVIRONMENT_NOT_EVALUATED]));
    assert_eq!(e.eval.status, NOT_DETERMINABLE);
}

#[test]
fn p_thermal_and_life_never_support_a_non_closure_in_a2() {
    let mut inp = synthetic_chain();
    for t in inp.thermal.per_state.as_mut().unwrap().values_mut() {
        t.margin_k = Some(10.0);
    }
    inp.life.firing_life_h = Some(1000.0);
    let o = evaluate(&inp).unwrap();
    for m in [Mode::AirPrimary, Mode::XeContingency] {
        for id in ["NH-THERMAL", "NH-LIFE"] {
            assert!(constraint(&o, m, id).iter().all(|c| c.status == NON_CLOSING && !c.eligible_non_close), "{id}");
        }
    }
    // A non-converged thermal output stays OPEN.
    for t in inp.thermal.per_state.as_mut().unwrap().values_mut() {
        t.converged = false;
        t.codes = vec!["NOT_CONVERGED".into()];
    }
    let o = evaluate(&inp).unwrap();
    assert!(constraint(&o, Mode::XeContingency, "NH-THERMAL").iter().all(|c| c.status == OPEN));
}

// ------------------------------------------------------------------------------------------------ pins

fn copy_into(tmp: &Path, rels: &[&str]) {
    for rel in rels {
        let dst = tmp.join(rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo().join(rel), dst).unwrap();
    }
}

fn tamper(tmp: &Path, rel: &str) {
    let p = tmp.join(rel);
    let mut b = std::fs::read(&p).unwrap();
    let n = b.len();
    b[n / 2] ^= 1;
    std::fs::write(p, b).unwrap();
}

fn scratch(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("abep_closure_m1_{name}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

#[test]
fn a2_and_a1_pins_are_verified() {
    let t = scratch("a2");
    let files = [A2_REL, A2_MD_REL, A2_LOCK_REL, env::PREREG_REL, env::LOCK_REL];
    copy_into(&t, &files);
    verify_a2(&t).unwrap();
    for f in files {
        let t2 = scratch("a2t");
        copy_into(&t2, &files);
        tamper(&t2, f);
        assert!(verify_a2(&t2).is_err(), "{f}");
        let _ = std::fs::remove_dir_all(&t2);
    }
    assert!(!a1_on_line(&t).unwrap());
    std::fs::write(t.join(A1_REL), b"{}").unwrap();
    assert!(a1_on_line(&t).is_err(), "A1 without its md and lock");
    let t3 = scratch("a1");
    copy_into(&t3, &[A1_REL, A1_MD_REL, A1_LOCK_REL]);
    assert!(a1_on_line(&t3).unwrap(), "A1 proper supersedes the identity A2 names");
    tamper(&t3, A1_REL);
    assert!(a1_on_line(&t3).is_err(), "A1 with other bytes");
    let _ = std::fs::remove_dir_all(&t3);
    let _ = std::fs::remove_dir_all(&t);
    assert!(base().a1_on_line, "A1 is on this line");
}

#[test]
fn f7_f8_and_plenum_records_are_pinned() {
    use abep_assess::closure_m1::gather::*;
    let files = [F7_REPORT_REL, F7_PARETO_REL, F8_REPORT_REL, F8_STUDY_REL, PLENUM_V8_REL, env::PREREG_REL];
    let t = scratch("flow");
    copy_into(&t, &files);
    let f = flow_path(&t).unwrap();
    assert!(f.robust_members.is_empty());
    assert_eq!(f, base().flow);
    for rel in files {
        let t2 = scratch("flowt");
        copy_into(&t2, &files);
        tamper(&t2, rel);
        assert!(flow_path(&t2).is_err(), "{rel}");
        let _ = std::fs::remove_dir_all(&t2);
    }
    let _ = std::fs::remove_dir_all(&t);
}

#[test]
fn p_air_bounded_launch_path_is_information_only() {
    let mut inp = synthetic_chain();
    let mut a = air(&[("G1", 1e-6, 0.030, 3.0), ("G2", 3e-6, 0.030, 1.0)]);
    a.bounded = true;
    with_air(&mut inp, a);
    let o = evaluate(&inp).unwrap();
    for id in ["HALL_T12_AT_PBUS", "HALL_T25_CAPABILITY"] {
        for c in constraint(&o, Mode::AirPrimary, id) {
            assert_eq!(c.status, NOT_DETERMINABLE_IN_ENVELOPE);
            assert!(!c.eligible_close && !c.eligible_non_close);
            assert!(c.codes.contains(&AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE.to_string()));
            assert!(c.detail.starts_with("BOUNDED_INFORMATION_CLOSES_AT_ALL_CORNERS"));
        }
    }
    assert!(substituted(&inp, &o).classification != SELECT_WITH_EVIDENCE_CONDITIONS);
}
#[test]
fn committed_dry_run_is_the_harness_v2_record_of_today() {
    let rel = format!("{NP_DIR}/closure_run_m1_dryrun_v1.json");
    let text = std::fs::read_to_string(repo().join(&rel)).unwrap();
    let v = abep_types::pyjson::loads(&text).unwrap();
    assert_eq!(st(at(&v, &["schema"])), SCHEMA);
    assert_eq!(st(at(&v, &["run_label"])), "M1_DRY_RUN_NOT_DECISIVE");
    assert_eq!(st(at(&v, &["addendum_a2", "sha256"])), A2_SHA256);
    assert_eq!(st(at(&v, &["classification", "result"])), NOT_DETERMINABLE);
    assert_eq!(st(at(&v, &["classification", "procedure_step"])), "C1");
    let commit = st(at(&v, &["rust_commit"])).to_string();
    // Regenerating today with the recorded commit reproduces the classification and the blocking list.
    let mut inp = base().clone();
    inp.today.mission.provenance.rust_commit = commit;
    // The v1 dry run predates addendum A5: it is the harness without A5 (dry run v2 carries A5).
    inp.a5 = None;
    let now = record_v2(&inp, &evaluate(&inp).unwrap(), "M1_DRY_RUN_NOT_DECISIVE");
    assert_eq!(at(&now, &["classification"]), at(&v, &["classification"]));
    assert_eq!(at(&now, &["readiness"]), at(&v, &["readiness"]));
}

/// Addendum A6: with an A6 XE envelope the XE_CONTINGENCY Hall constraints are HALL_XE_T12_AT_PBUS and
/// HALL_XE_T25_CAPABILITY_AT_PBUS over the A6 points; degenerate discharges (T > 0 but far below HC-01) never pass.
#[test]
fn a6_xe_envelope_carries_the_non_degenerate_xe_tests() {
    let cs = env::load_case_set(&repo()).unwrap();
    let synthetic = |t: f64, pd: f64| -> Envelope {
        let points = cs
            .cases
            .iter()
            .filter(|c| c.family == Family::Xe)
            .map(|c| EnvelopePoint {
                case: c.clone(),
                status: RunStatus::Pass,
                thrust_n: Some(t),
                discharge_power_w: Some(pd),
                discharge_current_a: Some(pd / c.vd_v),
                ion_current_a: None,
                te_max_ev: None,
            })
            .collect();
        Envelope {
            manifest_rel: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
            manifest_sha256: "SYNTHETIC".into(),
            raw_sha256: "SYNTHETIC".into(),
            cases_sha256: "SYNTHETIC".into(),
            bz_family_kind: cs.bz_family_kind,
            points,
        }
    };
    let lim = base().today.limits;
    let mut inp = base().clone();
    inp.xe_a6 = Some(synthetic(1e-18, 1e-13));
    let h = hall_tests(&inp, Mode::XeContingency, &lim);
    let ids: Vec<&str> = h.iter().map(|r| r.constraint.id.as_str()).collect();
    assert_eq!(ids, ["HALL_XE_T12_AT_PBUS", "HALL_XE_T25_CAPABILITY_AT_PBUS"]);
    assert!(h.iter().all(|r| r.constraint.status != CLOSES_IN_ENVELOPE), "degenerate discharges never close");
    inp.xe_a6 = Some(synthetic(0.030, 900.0));
    let h = hall_tests(&inp, Mode::XeContingency, &lim);
    assert!(h.iter().all(|r| r.constraint.status == CLOSES_IN_ENVELOPE && r.constraint.eligible_close));
    assert!(h[0].constraint.evidence_conditions.iter().any(|e| e == EC_NUM_A6));
    let out = evaluate(&inp).unwrap();
    assert!(!constraint(&out, Mode::XeContingency, "HALL_XE_T12_AT_PBUS").is_empty());
    let rec = record_v2(&inp, &out, "TEST");
    assert!(st(at(&rec, &["xe_hall_source"])).starts_with("A6"));
}
