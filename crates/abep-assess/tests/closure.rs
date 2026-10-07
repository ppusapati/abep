//! NP-HALL-PARAMETRIC-ENVELOPE v1: the decisive 196-state closure run today (no envelope) and the A9.32 classification
//! procedure on SYNTHETIC fixtures. Every fixture point carries SYNTHETIC_TEST_DATA_NOT_EVIDENCE semantics: it lives
//! only in this test and never in a record.

use abep_assess::closure::*;
use abep_hall::envelope::{self as env, BzFamilyKind, CaseInfo, Envelope, EnvelopePoint, Family, RunStatus};
use abep_mission::integration::Mode;
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::Value;
use std::collections::BTreeMap;
use std::sync::OnceLock;

fn repo() -> std::path::PathBuf {
    workspace_repo_root().unwrap()
}

fn today() -> &'static Value {
    static R: OnceLock<Value> = OnceLock::new();
    R.get_or_init(|| closure_record(&repo(), None, "test").unwrap())
}

fn at<'a>(v: &'a Value, path: &[&str]) -> &'a Value {
    path.iter().fold(v, |x, k| x.as_dict().unwrap_or_else(|| panic!("{k}")).get(k).unwrap_or_else(|| panic!("{k}")))
}

fn st(v: &Value) -> &str {
    v.as_str().unwrap()
}

#[test]
fn today_no_envelope_is_not_determinable_with_hall_envelope_not_run() {
    let r = today();
    assert_eq!(st(at(r, &["classification", "result"])), NOT_DETERMINABLE);
    assert_eq!(st(at(r, &["classification", "procedure_step"])), "C1");
    let codes: Vec<&str> =
        at(r, &["classification", "blockers"]).as_list().unwrap().iter().map(|b| st(at(b, &["code"]))).collect();
    for c in
        [HALL_ENVELOPE_NOT_RUN, AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED, BUS_LEDGER_NOT_COMPLETE, MASS_INCOMPLETE_EVIDENCE]
    {
        assert!(codes.contains(&c), "{c} missing from {codes:?}");
    }
    assert_eq!(st(at(r, &["envelope", "reason"])), HALL_ENVELOPE_NOT_RUN);
    assert_eq!(st(at(r, &["inputs", "credible_set"])), "EMPTY");
    assert_eq!(at(r, &["inputs", "n_states"]), &Value::int(196));
}

#[test]
fn today_every_layer_a_hall_field_is_not_evaluated_envelope_not_run() {
    let r = today();
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
        for h in at(r, &["hall_specific_closure_a", m]).as_list().unwrap() {
            let c = at(h, &["constraint"]);
            assert_eq!(st(at(c, &["status"])), NOT_EVALUATED);
            let codes: Vec<&str> = at(c, &["codes"]).as_list().unwrap().iter().map(st).collect();
            assert!(codes.contains(&HALL_ENVELOPE_NOT_RUN), "{m}: {codes:?}");
            assert_eq!(st(at(h, &["layer"])), env::LAYER_A_LABEL);
        }
        assert_eq!(at(r, &["layer_a_counts", m, "n_physics_feasible_a"]), &Value::int(0));
        assert_eq!(at(r, &["layer_a_counts", m, "n_physics_non_closing_a"]), &Value::int(0));
        assert_eq!(at(r, &["layer_b", "n_states_evidence_qualified_b", m]), &Value::int(0));
    }
    let states = at(r, &["states"]).as_list().unwrap();
    assert_eq!(states.len(), 196);
    for s in states {
        for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
            assert_eq!(st(at(s, &["modes", m, "layer_a", "status"])), NOT_DETERMINABLE);
            assert_eq!(st(at(s, &["modes", m, "layer_b", "status"])), NOT_EVALUATED);
            assert_eq!(st(at(s, &["modes", m, "layer_b", "mission_fields", "thrust_N"])), NOT_EVALUATED);
        }
    }
    assert_eq!(st(at(r, &["layer_b", "hall"])), "NOT_EVALUATED: credible Hall transport set EMPTY");
}

#[test]
fn today_planning_mass_never_makes_a_non_closure() {
    let r = today();
    for m in ["AIR_PRIMARY", "XE_CONTINGENCY"] {
        let mass = at(r, &["non_hall_closure_a", m])
            .as_list()
            .unwrap()
            .iter()
            .find(|c| st(at(c, &["id"])) == "NH-MASS")
            .unwrap();
        assert_eq!(st(at(mass, &["status"])), OPEN);
        assert_eq!(at(mass, &["eligible_non_close"]), &Value::Bool(false));
    }
}

// ------------------------------------------------------------------------------------------- synthetic fixtures

const SYNTHETIC: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";

fn lim() -> HallLimits {
    HallLimits { thrust_min_n: 0.012, thrust_capability_n: 0.025, p_bus_max_w: 1500.0, p_non_hall_lb_w: 0.0 }
}

fn point(fam: Family, geom: &str, tr: &str, status: RunStatus, t: f64, p: f64, i: usize) -> EnvelopePoint {
    EnvelopePoint {
        case: CaseInfo {
            key: format!("{SYNTHETIC}|{}|{geom}|{tr}|{i}", fam.as_str()),
            family: fam,
            geometry_id: geom.into(),
            bz_shape_id: "BZ-SYN".into(),
            b_peak_id: "BP".into(),
            vd_id: "VD".into(),
            mdot_id: "MF".into(),
            transport_id: tr.into(),
            vd_v: 300.0,
            mdot_kg_s: 1e-6,
            b_peak_t: 0.02,
            case_sha256: SYNTHETIC.into(),
        },
        status,
        thrust_n: (status == RunStatus::Pass).then_some(t),
        discharge_power_w: (status == RunStatus::Pass).then_some(p),
        discharge_current_a: (status == RunStatus::Pass).then_some(p / 300.0),
        te_max_ev: None,
    }
}

fn closes(id: &str) -> Constraint {
    Constraint {
        id: id.into(),
        hall_specific: false,
        status: CLOSES,
        eligible_close: true,
        eligible_non_close: false,
        codes: vec![],
        detail: SYNTHETIC.into(),
        evidence_conditions: vec![format!("EC-{id} ({SYNTHETIC})")],
    }
}

fn states(n: usize) -> Vec<StateRef> {
    (0..n).map(|i| StateRef { state_id: format!("{SYNTHETIC}-{i}"), required: true }).collect()
}

fn hall_for(pts: &[EnvelopePoint], bz: BzFamilyKind) -> BTreeMap<Mode, Vec<HallTestResult>> {
    let refs: Vec<&EnvelopePoint> = pts.iter().collect();
    let mut h = BTreeMap::new();
    for m in REQUIRED_MODES {
        // The fixture gives both required modes an evaluated Hall family (a future version with a Hall air chemistry).
        let fam = if m == Mode::AirPrimary { Family::N2Proxy } else { Family::Xe };
        let fp: Vec<&EnvelopePoint> = refs.iter().copied().filter(|p| p.case.family == fam).collect();
        h.insert(m, HallTest::of_mode(m).iter().map(|t| evaluate_hall_test(*t, fam, &fp, &lim(), bz)).collect());
    }
    h
}

fn non_hall(all_close: bool) -> BTreeMap<Mode, Vec<Constraint>> {
    let mut nh = BTreeMap::new();
    for m in REQUIRED_MODES {
        let ids: &[&str] = if m == Mode::AirPrimary {
            &["NH-FLOW", "NH-ICP", "NH-PBUS", "NH-TD", "NH-MASS"]
        } else {
            &["NH-FLOW", "NH-ICP"]
        };
        let v = ids
            .iter()
            .map(|id| {
                if all_close || *id != "NH-ICP" {
                    closes(id)
                } else {
                    Constraint::open(id, vec!["NP_ICP_NOT_ADMITTED".into()], SYNTHETIC)
                }
            })
            .collect();
        nh.insert(m, v);
    }
    nh
}

fn inputs(pts: &[EnvelopePoint], bz: BzFamilyKind, all_close: bool) -> ClosureInputs {
    ClosureInputs {
        credible_set_empty: true,
        envelope_ingested: true,
        bz_family_kind: Some(bz),
        hall: hall_for(pts, bz),
        non_hall: non_hall(all_close),
        states: states(3),
    }
}

fn closing_points() -> Vec<EnvelopePoint> {
    vec![
        point(Family::N2Proxy, "G1", "sgb-a", RunStatus::Pass, 0.030, 1400.0, 0),
        point(Family::N2Proxy, "G1", "sgb-b", RunStatus::Pass, 0.013, 900.0, 1),
        point(Family::N2Proxy, "G2", "sgb-a", RunStatus::NotSustained, 0.0, 0.0, 2),
        point(Family::Xe, "G1", "sgb-a", RunStatus::Pass, 0.008, 600.0, 3),
        point(Family::Xe, "G2", "sgb-a", RunStatus::OutOfDomain, 0.0, 0.0, 4),
    ]
}

#[test]
fn synthetic_closing_fixture_selects_with_evidence_conditions() {
    let out = classify(&inputs(&closing_points(), BzFamilyKind::SourcedSurrogate, true));
    assert_eq!(out.classification, SELECT_WITH_EVIDENCE_CONDITIONS);
    assert_eq!(out.step, "C3");
    assert_eq!(out.common_hardware, vec![("G1".to_string(), "BZ-SYN".to_string())]);
    assert!(out.evidence_conditions.iter().any(|e| e.starts_with("EC-TRANSPORT")));
    assert!(out.evidence_conditions.iter().any(|e| e.starts_with("EC-BZ")), "surrogate B(z) carries EC-BZ");
    assert!(out.states.iter().all(|(_, m)| m.values().all(|e| e.status == PHYSICS_FEASIBLE)));
}

#[test]
fn synthetic_non_closing_fixture_with_registered_bz_is_physically_non_closing() {
    let pts = vec![
        point(Family::N2Proxy, "G1", "sgb-a", RunStatus::Pass, 0.006, 1400.0, 0),
        point(Family::N2Proxy, "G1", "sgb-b", RunStatus::NotSustained, 0.0, 0.0, 1),
        point(Family::N2Proxy, "G2", "sgb-a", RunStatus::Pass, 0.020, 1600.0, 2),
        point(Family::Xe, "G1", "sgb-a", RunStatus::Pass, 0.004, 500.0, 3),
    ];
    let out = classify(&inputs(&pts, BzFamilyKind::H1Registered, true));
    assert_eq!(out.classification, PHYSICALLY_NON_CLOSING);
    assert_eq!(out.step, "C2");
    // The same physics under the sourced surrogate is not eligible: NOT_DETERMINABLE with the B(z) blocker.
    let out = classify(&inputs(&pts, BzFamilyKind::SourcedSurrogate, true));
    assert_eq!(out.classification, NOT_DETERMINABLE);
    let codes: Vec<&str> = out.blockers.iter().map(|(c, _)| c.as_str()).collect();
    assert!(codes.contains(&H1_BZ_NOT_REGISTERED) && codes.contains(&HALL_NON_CLOSING_UNDER_SURROGATE_BZ));
    assert_eq!(category(H1_BZ_NOT_REGISTERED), "DESIGN_VARIABLE_LIMIT");
}

#[test]
fn synthetic_open_input_fixture_is_not_determinable_with_its_blockers() {
    let out = classify(&inputs(&closing_points(), BzFamilyKind::H1Registered, false));
    assert_eq!(out.classification, NOT_DETERMINABLE);
    assert_eq!(out.step, "C4");
    assert_eq!(out.blockers, vec![("NP_ICP_NOT_ADMITTED".to_string(), 6)]);
    assert!(out.states.iter().all(|(_, m)| m.values().all(|e| e.status == NOT_DETERMINABLE)));
}

#[test]
fn unknown_points_never_make_a_non_closure() {
    let pts = vec![
        point(Family::N2Proxy, "G1", "sgb-a", RunStatus::Pass, 0.006, 900.0, 0),
        point(Family::N2Proxy, "G1", "sgb-b", RunStatus::OutOfDomain, 0.0, 0.0, 1),
        point(Family::Xe, "G1", "sgb-a", RunStatus::NumericalFailure, 0.0, 0.0, 2),
    ];
    let inp = inputs(&pts, BzFamilyKind::H1Registered, true);
    let air = &inp.hall[&Mode::AirPrimary][0].constraint;
    assert_eq!(air.status, NOT_DETERMINABLE_IN_ENVELOPE);
    assert!(air.codes.contains(&HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS.to_string()));
    assert_eq!(category(HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS), "MODEL_DOMAIN_LIMIT");
    let out = classify(&inp);
    assert_eq!(out.classification, NOT_DETERMINABLE);
}

#[test]
fn power_test_is_strict_and_uses_the_non_hall_lower_bound() {
    let p = point(Family::Xe, "G1", "sgb-a", RunStatus::Pass, 0.013, 1500.0, 0);
    assert!(!point_passes(HallTest::T12, &p, &lim()), "P_bus < 1500 W is strict");
    let p = point(Family::Xe, "G1", "sgb-a", RunStatus::Pass, 0.013, 1400.0, 0);
    assert!(point_passes(HallTest::T12, &p, &lim()));
    let with_lb = HallLimits { p_non_hall_lb_w: 150.0, ..lim() };
    assert!(!point_passes(HallTest::T12, &p, &with_lb));
    let ns = point(Family::Xe, "G1", "sgb-a", RunStatus::NotSustained, 0.0, 0.0, 0);
    assert!(!point_passes(HallTest::XeFunc, &ns, &lim()), "only PASS points count");
}

#[test]
fn credible_set_non_empty_and_missing_common_hardware_are_not_determinable() {
    let mut inp = inputs(&closing_points(), BzFamilyKind::H1Registered, true);
    inp.credible_set_empty = false;
    let out = classify(&inp);
    assert_eq!((out.classification, out.step), (NOT_DETERMINABLE, "C0"));
    let pts = vec![
        point(Family::N2Proxy, "G1", "sgb-a", RunStatus::Pass, 0.030, 1400.0, 0),
        point(Family::Xe, "G2", "sgb-a", RunStatus::Pass, 0.008, 600.0, 1),
    ];
    let out = classify(&inputs(&pts, BzFamilyKind::H1Registered, true));
    assert_eq!(out.classification, NOT_DETERMINABLE);
    assert_eq!(out.blockers[0].0, HALL_NO_COMMON_HARDWARE);
}

#[test]
fn synthetic_xe_envelope_through_the_production_record_keeps_air_not_evaluated() {
    // Real case set, synthetic outcomes: every Xe point PASS at 900 W and 10 mN; N2_PROXY points NOT_SUSTAINED.
    let r = repo();
    let cs = env::load_case_set(&r).unwrap();
    let points = cs
        .cases
        .iter()
        .map(|c| {
            let pass = c.family == Family::Xe;
            EnvelopePoint {
                case: c.clone(),
                status: if pass { RunStatus::Pass } else { RunStatus::NotSustained },
                thrust_n: pass.then_some(0.010),
                discharge_power_w: pass.then_some(900.0),
                discharge_current_a: pass.then_some(3.0),
                te_max_ev: None,
            }
        })
        .collect();
    let e = Envelope {
        manifest_rel: SYNTHETIC.into(),
        manifest_sha256: SYNTHETIC.into(),
        raw_sha256: SYNTHETIC.into(),
        cases_sha256: cs.sha256.clone(),
        bz_family_kind: cs.bz_family_kind,
        points,
    };
    let rec = closure_record(&r, Some(&e), "test").unwrap();
    let xe = &at(&rec, &["hall_specific_closure_a", "XE_CONTINGENCY"]).as_list().unwrap()[0];
    assert_eq!(st(at(xe, &["constraint", "status"])), CLOSES_IN_ENVELOPE);
    let air = &at(&rec, &["hall_specific_closure_a", "AIR_PRIMARY"]).as_list().unwrap()[0];
    assert_eq!(st(at(air, &["constraint", "status"])), NOT_EVALUATED);
    let air_codes: Vec<&str> = at(air, &["constraint", "codes"]).as_list().unwrap().iter().map(st).collect();
    assert_eq!(air_codes, vec![AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED]);
    assert_eq!(st(at(&rec, &["classification", "result"])), NOT_DETERMINABLE);
    assert_eq!(st(at(&rec, &["classification", "procedure_step"])), "C4");
    // N2_PROXY is diagnostic only: NON_CLOSING_IN_ENVELOPE under the surrogate, never eligible.
    let n2 = &at(&rec, &["n2_proxy_diagnostic", "tests"]).as_list().unwrap()[0];
    assert_eq!(st(at(n2, &["constraint", "status"])), NON_CLOSING_IN_ENVELOPE);
    assert_eq!(at(n2, &["constraint", "eligible_non_close"]), &Value::Bool(false));
    assert_eq!(at(&rec, &["layer_b", "n_states_evidence_qualified_b", "XE_CONTINGENCY"]), &Value::int(0));
}
