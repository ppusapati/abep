//! Governed Hall state on the real repository (A9.29 sec. 9, CLAUDE.md rule 9: asserted explicitly, never skipped):
//! the credible transport set is EMPTY, the nine screening candidates are never admitted, and every output needing
//! Hall performance is NOT_EVALUATED with the reason "credible Hall transport set EMPTY". Plus the schema / record-key
//! consistency checks of the contract's schema_parity section.

use abep_hall::py::{self, PyValue};
use abep_hall::registry::{BLOCK_KEYS, REGISTRATION_KEYS, WITHDRAWAL_KEYS};
use abep_hall::schema::{self, REQUIRED_FIELDS_V1, REQUIRED_META_V1};
use abep_hall::status::{HallGate, CREDIBLE_SET_EMPTY_REASON};
use abep_hall::{ensemble, hall_map, status};
use abep_provenance::workspace_repo_root;
use abep_types::EvalStatus;

fn repo() -> String {
    workspace_repo_root().unwrap().to_string_lossy().into_owned()
}

fn tmp_dir(tag: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!("abep_hall_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

#[test]
fn credible_transport_set_is_empty_and_hall_performance_is_not_evaluated() {
    let gate = HallGate::from_repository(&repo()).expect("repository ensemble validates");
    assert_eq!(gate.status, EvalStatus::NotEvaluated);
    assert_eq!(gate.reason.as_deref(), Some(CREDIBLE_SET_EMPTY_REASON));
    assert_eq!(CREDIBLE_SET_EMPTY_REASON, "credible Hall transport set EMPTY");
    assert!(gate.admitted_members.is_empty());
    let thrust = gate.gate(|| 0.012);
    assert_eq!(thrust.status, EvalStatus::NotEvaluated);
    assert_eq!(thrust.reason.as_deref(), Some("credible Hall transport set EMPTY"));
    assert_eq!(thrust.value, None, "no Hall performance value exists while the credible set is EMPTY");
}

#[test]
fn no_screening_candidate_is_ever_admitted() {
    let r = repo();
    let e = ensemble::load_ensemble(&r, None).unwrap();
    assert!(ensemble::member_ids(&e).unwrap().is_empty());
    let screening: Vec<String> = ensemble::screening_ids(&e).unwrap().iter().map(py::py_str).collect();
    let mut sorted = screening.clone();
    sorted.sort();
    let want: Vec<String> = (1..=9).map(|i| format!("sgb-screen-{i:02}")).collect();
    assert_eq!(sorted, want);
    for id in &want {
        let err = ensemble::require_admitted(id, &e).unwrap_err();
        assert_eq!(err.code, "REQ_SCREENING");
        assert_eq!(err.status(), EvalStatus::NotEvaluated);
        assert!(err.message.contains("is a SCREENING candidate"), "{}", err.message);
    }
    for cand in py::iterate(py::getitem(&e, "screening_candidates").unwrap()).unwrap() {
        let a = py::getitem(py::getitem(&cand, "transport_parameters").unwrap(), "anom_scale").unwrap();
        assert!(matches!(a, PyValue::Float(x) if *x <= 1.0 / 16.0), "physical prior a <= 1/16");
    }
}

#[test]
fn hall_response_status_reads_empty_set_and_inconclusive_p5_n2_v1() {
    let st = status::hall_response_status(&repo()).unwrap();
    assert_eq!(py::py_str(py::getitem(&st, "credible_set").unwrap()), "EMPTY");
    assert!(!py::getitem(&st, "admitted_members").unwrap().truthy());
    let dec = py::getitem(&st, "p5_n2_v1_decision").unwrap();
    assert!(!py::getitem(dec, "promotable").unwrap().truthy(), "P5-N2 v1: no candidate PROMOTABLE");
    assert_eq!(py::iterate(py::getitem(dec, "inconclusive").unwrap()).unwrap().len(), 9, "all nine INCONCLUSIVE");
}

fn synthetic_map(dir: &std::path::Path, member: &str, pin: &str) -> String {
    let s = schema::repo_schema(&repo()).unwrap();
    let mut meta: Vec<String> = s.meta.iter().map(|k| format!("\"{k}\": \"synthetic\"")).collect();
    meta.retain(|m| {
        !["\"schema\"", "\"pinned\"", "\"ensemble_member_id\"", "\"ion_wall_losses\""].iter().any(|k| m.starts_with(k))
    });
    meta.push("\"schema\": \"hall_map_schema_v1\"".into());
    meta.push(format!("\"pinned\": \"commit = \\\"{pin}\\\"\""));
    meta.push(format!("\"ensemble_member_id\": \"{member}\""));
    meta.push("\"ion_wall_losses\": true".into());
    meta.push("\"evidence_status\": \"SYNTHETIC_TEST_ONLY_NOT_EVIDENCE\"".into());
    let fields: Vec<String> = s
        .fields
        .iter()
        .map(|f| {
            let v =
                if ["converged", "sustained", "chemistry_trustworthy", "wall_life_trustworthy"].contains(&f.as_str()) {
                    "[[1, 1], [1, 0]]"
                } else {
                    "[[0.5, 1.5], [2.5, 3.5]]"
                };
            format!("\"{f}\": {v}")
        })
        .collect();
    let doc = format!(
        "{{\"meta\": {{{}}}, \"axes\": {{\"Vd\": [250.0, 300.0], \"mdot_kgps\": [1e-06, 2e-06]}}, \"fields\": {{{}}}}}",
        meta.join(", "),
        fields.join(", ")
    );
    let p = dir.join("map.json");
    std::fs::write(&p, doc).unwrap();
    p.to_string_lossy().into_owned()
}

#[test]
fn maps_of_screening_candidates_or_other_pins_are_refused() {
    let r = repo();
    let pin = hall_map::pinned_commit(&r, None).unwrap();
    assert_eq!(pin, "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5");
    let d = tmp_dir("refuse");
    let p = synthetic_map(&d, "sgb-screen-01", &pin);
    let err = hall_map::HallMap::load(&r, &p, None, None).unwrap_err();
    assert_eq!((err.code, err.status()), ("HM_NOT_ADMITTED", EvalStatus::NotEvaluated));
    let mut ens = ensemble::load_ensemble(&r, None).unwrap();
    py::set_item(
        &mut ens,
        "members",
        PyValue::List(vec![py::dict([("ensemble_member_id", py::s("synthetic-member"))])]),
    );
    let p = synthetic_map(&d, "synthetic-member", &"0".repeat(40));
    let err = hall_map::HallMap::load(&r, &p, None, Some(&ens)).unwrap_err();
    assert_eq!((err.code, err.status()), ("HM_NOT_PINNED", EvalStatus::ModelError));
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
fn synthetic_map_query_applies_the_trust_rules() {
    let r = repo();
    let d = tmp_dir("query");
    let mut ens = ensemble::load_ensemble(&r, None).unwrap();
    py::set_item(
        &mut ens,
        "members",
        PyValue::List(vec![py::dict([("ensemble_member_id", py::s("synthetic-member"))])]),
    );
    let p = synthetic_map(&d, "synthetic-member", &hall_map::pinned_commit(&r, None).unwrap());
    let m = hall_map::HallMap::load(&r, &p, None, Some(&ens)).unwrap();
    let q = m.query(&[("Vd".into(), 275.0), ("mdot_kgps".into(), 1.5e-6)]).unwrap();
    let get = |k: &str| q.iter().find(|(n, _)| n == k).unwrap().1.clone();
    assert_eq!(get("thrust_N"), hall_map::QueryValue::Float(2.0));
    assert_eq!(get("trustworthy"), hall_map::QueryValue::Bool(false), "a surrounding node did not converge");
    assert_eq!(get("wall_life_trustworthy"), hall_map::QueryValue::Bool(false));
    let out = m.query(&[("Vd".into(), 350.0), ("mdot_kgps".into(), 1.5e-6)]).unwrap_err();
    assert_eq!(out.status(), EvalStatus::OutOfDomain, "no extrapolation");
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
fn field_sets_and_record_keys_match_the_schemas() {
    let r = repo();
    let s = schema::repo_schema(&r).unwrap();
    assert_eq!(s.fields, REQUIRED_FIELDS_V1.to_vec());
    assert_eq!(s.meta, REQUIRED_META_V1.to_vec());
    let reg = py::load_json_file(&py::join(&r, "schemas/hallmap/hallmap_registry_v1.json")).unwrap();
    let defs = py::getitem(&reg, "$defs").unwrap();
    let required = |def: &str| -> Vec<String> {
        py::iterate(py::getitem(py::getitem(defs, def).unwrap(), "required").unwrap())
            .unwrap()
            .iter()
            .map(py::py_str)
            .collect()
    };
    assert_eq!(required("registration"), REGISTRATION_KEYS.to_vec());
    assert_eq!(required("withdrawal"), WITHDRAWAL_KEYS.to_vec());
    for (block, keys) in BLOCK_KEYS {
        let props = py::getitem(py::getitem(defs, "registration").unwrap(), "properties").unwrap();
        let props_w = py::getitem(py::getitem(defs, "withdrawal").unwrap(), "properties").unwrap();
        let mut node = py::get(props, block).unwrap().or(py::get(props_w, block).unwrap()).unwrap().clone();
        while let Some(PyValue::Str(rf)) = py::get(&node, "$ref").unwrap().cloned() {
            node = py::getitem(defs, rf.rsplit('/').next().unwrap()).unwrap().clone();
        }
        if let Some(PyValue::List(alts)) = py::get(&node, "oneOf").unwrap().cloned() {
            node = alts[0].clone();
        }
        let mut got: Vec<String> =
            py::iterate(py::getitem(&node, "required").unwrap()).unwrap().iter().map(py::py_str).collect();
        let mut want: Vec<String> = keys.iter().map(|k| k.to_string()).collect();
        got.sort();
        want.sort();
        assert_eq!(got, want, "{block}");
    }
}
