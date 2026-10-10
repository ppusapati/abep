//! Acceptance cases AC-01..AC-04 and AC-06..AC-10 of ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1 (the RFP constraint matrix
//! and the HC-05 evaluator) on the repository's admitted raw results. AC-05 (crate graph) is tests/crate_graph.rs.

use abep_assess::matrix::{constraint_matrix, to_json, RawPhysics, ASSESSMENT_WORDS, ROW_FIELDS};
use abep_assess::neutralization::{
    hc05, CapacityBasis, Current, MarginRule, NeutralizationInputs, ValidationCell, MARGIN_K_MIN,
};
use abep_assess::statewise::statewise_drag_compensation;
use abep_assess::Thresholds;
use abep_config::ConfigPaths;
use abep_icp::status::IcpStatus;
use abep_provenance::{sha256_hex, workspace_repo_root};
use abep_types::pyjson::{dumps, dumps_config_file, loads, py_str, DumpOptions, Value};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn raw() -> &'static RawPhysics {
    static R: OnceLock<RawPhysics> = OnceLock::new();
    R.get_or_init(|| RawPhysics::load_repository(&repo()))
}

fn thresholds() -> Thresholds {
    Thresholds::load(&ConfigPaths::repository(&repo())).unwrap()
}

fn g<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("key {k}"))
}

fn rows(m: &Value) -> Vec<Value> {
    g(m, "rows").as_list().unwrap().to_vec()
}

fn row<'a>(rs: &'a [Value], id: &str) -> &'a Value {
    rs.iter().find(|r| py_str(g(r, "id")) == id).unwrap()
}

fn status(r: &Value) -> String {
    py_str(g(g(r, "rfp_assessment_status"), "status"))
}

fn json(v: &Value) -> String {
    dumps(v, &DumpOptions::default()).unwrap()
}

fn matrix(t: &Thresholds, raw: &RawPhysics) -> Value {
    constraint_matrix(t, raw, &repo()).unwrap()
}

fn tokens(s: &str) -> Vec<&str> {
    s.split(|c: char| !(c.is_ascii_alphanumeric() || c == '_')).filter(|x| !x.is_empty()).collect()
}

fn keys(v: &Value, out: &mut Vec<String>) {
    match v {
        Value::Dict(d) => {
            for (k, x) in d.iter() {
                out.push(k.clone());
                keys(x, out);
            }
        }
        Value::List(l) => l.iter().for_each(|x| keys(x, out)),
        _ => {}
    }
}

#[test]
fn ac01_four_separate_fields_and_no_assessment_word_in_raw() {
    let m = matrix(&thresholds(), raw());
    let rs = rows(&m);
    assert_eq!(rs.len(), 8);
    for r in &rs {
        let names: Vec<&str> = r.as_dict().unwrap().keys().map(String::as_str).collect();
        assert_eq!(names, ROW_FIELDS.to_vec());
        let rawj = json(g(r, "raw_physics_result"));
        for w in ASSESSMENT_WORDS {
            assert!(!tokens(&rawj).contains(&w), "{} raw field carries assessment word {w}", py_str(g(r, "id")));
        }
        let mut ks = Vec::new();
        keys(g(r, "raw_physics_result"), &mut ks);
        assert!(ks.iter().all(|k| !k.contains("limit") && !k.contains("threshold")), "{ks:?}");
    }
}

/// A copy of config/ with edited values, the manifest re-hashed.
fn edited_config(tag: &str, edits: &[(&str, &[&str], Value)]) -> PathBuf {
    let src = repo().join("config");
    let dst = std::env::temp_dir().join(format!("abep-assess-cfg-{}-{tag}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dst);
    copy_dir(&src, &dst);
    let mut manifest = loads(&std::fs::read_to_string(dst.join("MANIFEST.json")).unwrap()).unwrap();
    for (rel, path, value) in edits {
        let p = dst.join(rel);
        let mut doc = loads(&std::fs::read_to_string(&p).unwrap()).unwrap();
        let mut cur = &mut doc;
        for k in *path {
            cur = match cur {
                Value::Dict(d) => d.get_mut(k).unwrap(),
                _ => panic!("path"),
            };
        }
        *cur = value.clone();
        let bytes = dumps_config_file(&doc).unwrap();
        std::fs::write(&p, &bytes).unwrap();
        if let Value::Dict(m) = &mut manifest {
            if let Some(Value::Dict(files)) = m.get_mut("files") {
                if let Some(Value::Dict(e)) = files.get_mut(rel) {
                    e.insert("sha256", Value::str(sha256_hex(&bytes)));
                    e.insert("bytes", Value::int(bytes.len() as i64));
                }
            }
        }
    }
    std::fs::write(dst.join("MANIFEST.json"), dumps_config_file(&manifest).unwrap()).unwrap();
    dst
}

fn copy_dir(a: &Path, b: &Path) {
    std::fs::create_dir_all(b).unwrap();
    for e in std::fs::read_dir(a).unwrap() {
        let e = e.unwrap();
        let p = e.path();
        if p.is_dir() {
            copy_dir(&p, &b.join(e.file_name()));
        } else {
            std::fs::copy(&p, b.join(e.file_name())).unwrap();
        }
    }
}

#[test]
fn ac02_threshold_change_moves_assessment_never_raw_physics() {
    let base = thresholds();
    let dir = edited_config(
        "ac02",
        &[
            (
                "constraints/engineering_constraints_v1.json",
                &["constraints", "wet_mass_max_kg", "value"],
                Value::int(50),
            ),
            ("assessment/gate_thresholds_v1.json", &["gates", "HC-08", "value"], Value::Float(0.001)),
        ],
    );
    let edited = Thresholds::load(&ConfigPaths::with_config_root(&repo(), &dir)).unwrap();
    assert_eq!(edited.limit("HC-04"), Some(50.0));
    assert_eq!(edited.limit("HC-08"), Some(0.001));
    assert_eq!(base.limit("HC-04"), Some(40.0));
    let (m0, m1) = (matrix(&base, raw()), matrix(&edited, raw()));
    let (r0, r1) = (rows(&m0), rows(&m1));
    for (a, b) in r0.iter().zip(&r1) {
        assert_eq!(json(g(a, "raw_physics_result")), json(g(b, "raw_physics_result")), "raw physics moved");
    }
    assert_eq!(status(row(&r0, "RFP-WET-MASS-LT-40KG")), "DOES_NOT_CLOSE");
    assert_eq!(status(row(&r1, "RFP-WET-MASS-LT-40KG")), "INCOMPLETE_EVIDENCE");
    // the 196-state statewise run: synthetic T / D, identical inputs, statuses move with the HC-08 limit only
    let ds = raw().design_states.as_ref().unwrap();
    let states: Vec<Value> = ds
        .states
        .iter()
        .filter(|x| x.required)
        .map(|x| abep_types::pydict! { "state_id" => x.state_id.as_str() })
        .collect();
    assert_eq!(states.len(), 196);
    let rec = |i: usize, st: &Value, v: f64| -> Value {
        let _ = i;
        abep_types::pydict! {
            "state_id" => g(st, "state_id").clone(), "status" => "SYNTHETIC_TEST_DATA_NOT_EVIDENCE", "value_N" => v,
        }
    };
    let inputs_digest = |t: &[Value]| sha256_hex(json(&Value::List(t.to_vec())).as_bytes());
    let before = inputs_digest(&states);
    let run = |t: &Thresholds| {
        let mut tf = |i: usize, st: &Value| Ok(rec(i, st, 0.012 + 1e-5 * (i % 150) as f64));
        let mut df = |i: usize, st: &Value| Ok(rec(i, st, 0.012));
        statewise_drag_compensation(t, &states, &mut tf, &mut df, false).unwrap()
    };
    let (q0, q1) = (run(&base), run(&edited));
    assert_eq!(inputs_digest(&states), before);
    let per = |q: &Value| -> Vec<String> {
        g(q, "statewise").as_list().unwrap().iter().map(|p| py_str(g(p, "state_status"))).collect()
    };
    assert_ne!(per(&q0), per(&q1));
    assert_eq!(py_str(g(&q0, "status")), "MET_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE");
    assert_eq!(py_str(g(&q1, "status")), "VIOLATED_ON_SYNTHETIC_TEST_DATA_NOT_EVIDENCE");
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn ac03_todays_raw_results_are_fail_closed() {
    let m = matrix(&thresholds(), raw());
    let rs = rows(&m);
    for r in &rs {
        let s = status(r);
        assert!(s != "COMPLIES" && s != "DOES_NOT_COMPLY", "{s}");
    }
    let mass = row(&rs, "RFP-WET-MASS-LT-40KG");
    assert_eq!(status(mass), "DOES_NOT_CLOSE");
    assert_eq!(py_str(g(g(mass, "evidence_status"), "status")), "INCOMPLETE_EVIDENCE");
    let cases: Vec<f64> = g(g(mass, "rfp_assessment_status"), "per_case")
        .as_list()
        .unwrap()
        .iter()
        .map(|c| g(c, "xe_case_kg").to_f64().unwrap())
        .collect();
    assert_eq!(cases, vec![2.0, 5.0, 10.0]);
    for id in [
        "RFP-ALT",
        "RFP-ATM-PRIMARY",
        "RFP-XE-CONTINGENCY",
        "RFP-THRUST-12MN-SUSTAINED",
        "RFP-THRUST-25MN-CAPABILITY",
        "RFP-PBUS-LT-1500W",
        "RFP-ATM-XE-COMPATIBILITY",
    ] {
        assert_eq!(status(row(&rs, id)), "NOT_EVALUATED", "{id}");
    }
    let eg = g(&m, "engineering_gates");
    assert_eq!(py_str(g(g(eg, "HC-05"), "status")), "NOT_EVALUATED");
    assert_eq!(py_str(g(g(g(eg, "rvm_and_icp_gate"), "GNG-ICP-01"), "status")), "NOT_EVALUATED");
    let replay = g(g(eg, "rvm_and_icp_gate"), "rvm_replay");
    assert_eq!(g(replay, "cells"), g(replay, "reproduce_committed"));
}

fn current(v: f64, u: f64) -> Current {
    Current { value_a: Some(v), u_a: Some(u), status: IcpStatus::Converged, reasons: vec![] }
}

fn inputs(basis: CapacityBasis, ie: f64, cell: &str) -> NeutralizationInputs {
    NeutralizationInputs {
        point_id: Some("P-01".into()),
        capacity_basis: basis,
        i_e_cap: current(ie, 0.05),
        i_d_max_h1: Some(current(4.0, 0.05)),
        validation_cell: Some(ValidationCell { cell_id: "C-AR-01".into(), status: cell.into(), contains_point: true }),
        margin_rule: Some(MarginRule { k_one_sided: MARGIN_K_MIN, alpha_one_sided: 0.05, k_basis: "normal".into() }),
    }
}

fn hc(x: Option<&NeutralizationInputs>) -> (String, String) {
    let v = hc05(&thresholds(), x).unwrap();
    (py_str(g(&v, "status")), py_str(g(&v, "reason_code")))
}

#[test]
fn ac04_hc05_rule_order() {
    assert_eq!(hc(None).1, "NO_NEUTRALIZATION_RECORD");
    assert_eq!(hc(Some(&inputs(CapacityBasis::Synthetic, 6.0, "VALIDATED_BENCH"))).1, "SYNTHETIC_NOT_EVIDENCE");
    let mut x = inputs(CapacityBasis::Model, 6.0, "VALIDATED_BENCH");
    x.i_d_max_h1 = None;
    assert_eq!(hc(Some(&x)), ("NOT_EVALUATED".into(), "I_D_MAX_H1_NOT_REGISTERED".into()));
    let mut x = inputs(CapacityBasis::Model, 6.0, "VALIDATED_BENCH");
    x.i_e_cap.status = IcpStatus::IncompleteEvidence;
    assert_eq!(hc(Some(&x)).0, "INCOMPLETE_EVIDENCE");
    // A9.31 sec. 10: a verified model with full uncertainty but no VALIDATED_BENCH cell stays NOT_EVALUATED
    for cell in ["NOT_VALIDATED", "INCONSISTENT", "VERIFIED"] {
        let x = inputs(CapacityBasis::Model, 6.0, cell);
        assert_eq!(hc(Some(&x)), ("NOT_EVALUATED".into(), "MODEL_NOT_VALIDATED_IN_DOMAIN".into()));
    }
    let mut x = inputs(CapacityBasis::Model, 6.0, "VALIDATED_BENCH");
    x.validation_cell.as_mut().unwrap().contains_point = false;
    assert_eq!(hc(Some(&x)).1, "MODEL_NOT_VALIDATED_IN_DOMAIN");
    for f in [
        |x: &mut NeutralizationInputs| x.margin_rule = None,
        |x: &mut NeutralizationInputs| x.margin_rule.as_mut().unwrap().k_one_sided = 1.5,
        |x: &mut NeutralizationInputs| x.margin_rule.as_mut().unwrap().alpha_one_sided = 0.1,
        |x: &mut NeutralizationInputs| x.margin_rule.as_mut().unwrap().k_basis = " ".into(),
        |x: &mut NeutralizationInputs| x.i_e_cap.u_a = Some(0.0),
        |x: &mut NeutralizationInputs| x.i_d_max_h1.as_mut().unwrap().u_a = None,
    ] {
        let mut x = inputs(CapacityBasis::Measured, 6.0, "NOT_VALIDATED");
        f(&mut x);
        assert_eq!(hc(Some(&x)).1, "MARGIN_RULE_NOT_ADMISSIBLE");
    }
    // H-07: evaluated on a VALIDATED_BENCH cell or a measured point; M_n,LB decides, never the point M_n
    assert_eq!(hc(Some(&inputs(CapacityBasis::Model, 6.0, "VALIDATED_BENCH"))).0, "MET_ON_SUPPLIED_VALUES");
    assert_eq!(hc(Some(&inputs(CapacityBasis::Measured, 6.0, "NOT_VALIDATED"))).0, "MET_ON_SUPPLIED_VALUES");
    assert_eq!(hc(Some(&inputs(CapacityBasis::Measured, 3.0, "NOT_VALIDATED"))).0, "VIOLATED");
    // point M_n > 0 but M_n,LB <= 0: VIOLATED
    let x = inputs(CapacityBasis::Measured, 4.05, "NOT_VALIDATED");
    let v = hc05(&thresholds(), Some(&x)).unwrap();
    assert!(g(&v, "M_n").to_f64().unwrap() > 0.0 && g(&v, "M_n_LB").to_f64().unwrap() <= 0.0);
    assert_eq!(py_str(g(&v, "status")), "VIOLATED");
}

#[test]
fn ac06_no_requirement_parsing_in_raw_physics() {
    let physics = [
        "abep-data",
        "abep-atmos",
        "abep-intake",
        "abep-gaspath",
        "abep-chem",
        "abep-mission",
        "abep-subsystems",
        "abep-hall",
        "abep-julia-bridge",
        "abep-icp",
    ];
    let banned = ["assessment/gate_thresholds", "config/requirements/", "requirements/rfp_constraints", "rfp_official"];
    for c in physics {
        let dir = repo().join("crates").join(c).join("src");
        let mut stack = vec![dir];
        while let Some(d) = stack.pop() {
            for e in std::fs::read_dir(&d).unwrap() {
                let p = e.unwrap().path();
                if p.is_dir() {
                    stack.push(p);
                } else if p.extension().is_some_and(|x| x == "rs") {
                    let t = std::fs::read_to_string(&p).unwrap();
                    for b in banned {
                        assert!(!t.contains(b), "{} names {b}", p.display());
                    }
                }
            }
        }
    }
}

#[test]
fn ac07_ac08_deterministic_and_raw_unchanged() {
    let t = thresholds();
    let r = raw().clone();
    let before = r.canonical();
    let a = to_json(&matrix(&t, &r)).unwrap();
    let b = to_json(&matrix(&t, &r)).unwrap();
    assert_eq!(a, b);
    assert_eq!(r.canonical(), before);
    let fresh = RawPhysics::load_repository(&repo());
    assert_eq!(to_json(&matrix(&t, &fresh)).unwrap(), a);
}

#[test]
fn ac09_non_determining_records_never_comply() {
    let t = thresholds();
    let mut r = raw().clone();
    let rec = |status: &str, v: f64| abep_types::pydict! { "status" => status, "value" => v };
    r.thrust = rec("PARAMETRIC_SENSITIVITY_ONLY", 0.03);
    r.thrust_capability = rec("SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", 0.03);
    r.propellant_capability = rec("SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", 1.0);
    let mut bus = rec("SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", 900.0);
    if let Value::Dict(d) = &mut bus {
        d.insert("gate_verdict", Value::str("PASS"));
    }
    r.bus_objective = Ok(bus);
    r.wet_mass_objective = Ok(rec("PARAMETRIC_SENSITIVITY_ONLY", 30.0));
    let m = matrix(&t, &r);
    for row in rows(&m) {
        assert_ne!(status(&row), "COMPLIES", "{}", py_str(g(&row, "id")));
    }
    let hc = g(g(&m, "engineering_gates"), "hard_constraints");
    let st = |id: &str| py_str(g(hc.as_list().unwrap().iter().find(|c| py_str(g(c, "id")) == id).unwrap(), "status"));
    assert_eq!(st("HC-01"), "MET_ON_PARAMETRIC_VALUES_SENSITIVITY_ONLY_NOT_MET");
    assert_eq!(st("HC-02"), "MET_ON_SUPPLIED_VALUES");
    assert_eq!(st("HC-03"), "MET_ON_SUPPLIED_VALUES");
    // synthetic data is never evidence (NOT_EVALUATED); a parametric comparison is sensitivity only
    let rs = rows(&m);
    assert_eq!(status(row(&rs, "RFP-THRUST-25MN-CAPABILITY")), "NOT_EVALUATED");
    assert_eq!(status(row(&rs, "RFP-PBUS-LT-1500W")), "NOT_EVALUATED");
    assert_eq!(status(row(&rs, "RFP-THRUST-12MN-SUSTAINED")), "INCOMPLETE_EVIDENCE");
}

#[test]
fn ac10_tampered_records_fail_closed() {
    let tmp = std::env::temp_dir().join(format!("abep-assess-tamper-{}", std::process::id()));
    let rel = abep_subsystems::mass::v5::RECORD_REL;
    std::fs::create_dir_all(tmp.join(rel).parent().unwrap()).unwrap();
    let mut text = std::fs::read_to_string(repo().join(rel)).unwrap();
    text.push(' ');
    std::fs::write(tmp.join(rel), text).unwrap();
    let mut r = raw().clone();
    r.mass_record = abep_subsystems::mass::v5::load_record_pinned(&tmp).map_err(Into::into);
    r.mass_gates = abep_subsystems::mass::v5::mass_gates(&tmp, &abep_subsystems::mass::v5::MissionXeLoad::NotAdmitted)
        .map_err(Into::into);
    r.rvm = abep_assess::rvm::RvmRecord::load_pinned(&repo(), &"0".repeat(64));
    let m = matrix(&thresholds(), &r);
    let rs = rows(&m);
    assert_eq!(status(row(&rs, "RFP-WET-MASS-LT-40KG")), "MODEL_ERROR");
    assert_eq!(status(row(&rs, "RFP-XE-CONTINGENCY")), "MODEL_ERROR");
    assert_eq!(py_str(g(g(g(&m, "engineering_gates"), "rvm_and_icp_gate"), "status")), "MODEL_ERROR");
    let _ = std::fs::remove_dir_all(tmp);
}
