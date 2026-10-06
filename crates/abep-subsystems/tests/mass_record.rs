//! SC-WP-07 mass lane: the selected-flight mass record (mass_power_a9_v5) reproduced byte for byte, the A9.26 owner
//! arithmetic, the AL-07 value status (RM-R27), C1 never in the flight roll-up, the fail-closed gates and the wet-mass
//! objective (contracts docs/rust_migration/contracts/{K-MASS-RULES, C-DOCS_BUDGETS_MASS_POWER_A9_V5,
//! C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3}). Missing evidence is asserted as a fail-closed status, never skipped.

use abep_provenance::workspace_repo_root;
use abep_subsystems::mass::py::{gi, iter, num};
use abep_subsystems::mass::{pyfmt, rules, v5, wet_mass, xe};
use abep_types::pyjson::{self, loads, py_str, Value};
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn record() -> Value {
    v5::load_record_pinned(&root()).unwrap()
}

fn flight_lines(rec: &mut Value) -> &mut Vec<Value> {
    match rec {
        Value::Dict(d) => match d.get_mut("lines").unwrap() {
            Value::Dict(l) => match l.get_mut(rules::FLIGHT).unwrap() {
                Value::List(v) => v,
                _ => panic!("list"),
            },
            _ => panic!("dict"),
        },
        _ => panic!("dict"),
    }
}

fn set(line: &mut Value, key: &str, v: Value) {
    if let Value::Dict(d) = line {
        d.insert(key, v);
    }
}

fn line_mut<'a>(rec: &'a mut Value, lid: &str) -> &'a mut Value {
    flight_lines(rec).iter_mut().find(|x| py_str(gi(x, "line").unwrap()) == lid).unwrap()
}

#[test]
fn record_reproduces_byte_for_byte() {
    assert!(v5::check(&root()).unwrap().is_empty(), "the committed mass_power_a9_v5 record must reproduce");
    let (js, md) = v5::render(&root()).unwrap();
    assert_eq!(abep_provenance::sha256_hex(js.as_bytes()), v5::RECORD_SHA256);
    let (js2, md2) = v5::render(&root()).unwrap();
    assert_eq!((js, md), (js2, md2), "deterministic");
}

#[test]
fn owner_arithmetic_reproduced_exactly() {
    let rec = record();
    let roll = &iter(gi(&rec, "rollups").unwrap()).unwrap()[0];
    let g = |k: &str| num(gi(roll, k).unwrap()).unwrap();
    assert_eq!(g("nonharness_known_kg"), 33.1196);
    assert_eq!(g("harness_kg"), 1.743136842);
    assert_eq!(g("nominal_dry_known_kg"), 34.86273684);
    assert_eq!(g("system_margin_kg"), 3.486273684);
    assert_eq!(g("dry_known_kg"), 38.34901052);
    // dry = non-harness x (1 / 0.95) x line factors x system margin (line factors inside the MEV values)
    let nh = g("nonharness_known_kg");
    let dry = pyfmt::rk(pyfmt::rk(nh + pyfmt::rk(nh * 0.05 / 0.95)) * 1.1);
    assert_eq!(dry, 38.34901052);
    assert!((dry - nh / 0.95 * 1.1).abs() <= 5e-9 * dry);
    let mut hard = Vec::new();
    for w in iter(gi(roll, "wet").unwrap()).unwrap() {
        if py_str(gi(&w, "reference").unwrap()) == "HARD_40_WET" {
            hard.push((
                num(gi(&w, "xe_case_kg").unwrap()).unwrap(),
                num(gi(&w, "wet_known_kg").unwrap()).unwrap(),
                py_str(gi(&w, "state").unwrap()),
            ));
        }
    }
    assert_eq!(
        hard,
        vec![
            (2.0, 40.34901052, "DOES_NOT_CLOSE".to_string()),
            (5.0, 43.34901052, "DOES_NOT_CLOSE".to_string()),
            (10.0, 48.34901052, "DOES_NOT_CLOSE".to_string())
        ]
    );
    for (_, w, _) in &hard {
        assert!(w > &40.0, "no 40 kg closure is claimed");
    }
    for (c, owner) in v5::EXPECTED_WET {
        let w = hard.iter().find(|h| h.0 == c).unwrap().1;
        assert!((w - owner).abs() <= v5::MATERIAL_KG);
    }
    assert_eq!(py_str(gi(gi(&rec, "mass_status").unwrap(), "status").unwrap()), v5::MASS_STATUS);
}

#[test]
fn c1_never_in_the_flight_mass() {
    let rec = record();
    let lines = iter(gi(gi(&rec, "lines").unwrap(), rules::FLIGHT).unwrap()).unwrap();
    assert!(lines.iter().all(|x| py_str(gi(x, "line").unwrap()) != "AL-C1"));
    let rolls = iter(gi(&rec, "rollups").unwrap()).unwrap();
    assert_eq!(rolls.len(), 1);
    assert_eq!(py_str(gi(&rolls[0], "configuration").unwrap()), rules::FLIGHT);
    // the roll-up rules refuse a C1 line or a non-flight configuration outright (DIV-K01 / DIV-K02)
    let c1 = loads(r#"{"line": "AL-C1", "value": {"value_kg": 0.5, "governs": "ALLOCATION_MEV"}}"#).unwrap();
    let mut with_c1 = lines.clone();
    with_c1.insert(0, c1);
    let e = rules::rollup(&Value::str(rules::FLIGHT), &with_c1, &vec![], &vec![]).unwrap_err();
    assert_eq!(e.class, "MassError");
    let e = rules::rollup(&Value::str("hall_c1_reference"), &lines, &vec![], &vec![]).unwrap_err();
    assert!(e.message.contains("GROUND_REFERENCE_ONLY"));
}

#[test]
fn al07_value_status_preserved() {
    let vs = v5::al07_value_status(&root()).unwrap();
    assert_eq!(py_str(gi(&vs, "a9_28_value_status").unwrap()), "PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT");
    assert_eq!(py_str(gi(&vs, "a9_28_open_action").unwrap()), "AFI-02-RA1_OPEN");
    assert_eq!(gi(&vs, "value_kg").unwrap(), &Value::Float(6.0));
    assert_eq!(py_str(gi(&vs, "status").unwrap()), "INCOMPLETE_EVIDENCE");
    // any promotion of AL-07 to a CBE / measured / frozen value is refused (MODEL_ERROR)
    let mutations = [
        ("cbe_kg", "5.0"),
        ("measured_kg", "5.5"),
        ("value", r#"{"value_kg": 6.0, "governs": "MEV_FROM_CBE"}"#),
        ("value", r#"{"value_kg": 5.0, "governs": "MEV_PLANNING_FLOOR"}"#),
        ("afi_02_labels", r#"["PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR", "FROZEN_FLIGHT_TRUTH"]"#),
        ("open_rebase_action", r#"{"id": "AFI-02-RA1", "state": "CLOSED"}"#),
    ];
    for (key, value) in mutations {
        let mut rec = record();
        set(line_mut(&mut rec, "AL-07"), key, loads(value).unwrap());
        let e = v5::al07_value_status_of(&rec, &root()).unwrap_err();
        assert_eq!(abep_subsystems::mass::py::to_abep(e).status(), abep_types::EvalStatus::ModelError);
    }
}

#[test]
fn mass_gates_fail_closed() {
    let gates = v5::mass_gates(&root(), &v5::MissionXeLoad::NotAdmitted).unwrap();
    let g = iter(&gates).unwrap();
    assert_eq!(py_str(gi(&g[0], "status").unwrap()), "NOT_EVALUATED");
    assert_eq!(py_str(gi(&g[1], "status").unwrap()), "INCOMPLETE_EVIDENCE");
    assert_eq!(py_str(gi(&g[2], "status").unwrap()), "INCOMPLETE_EVIDENCE");
    let states = gi(&g[1], "hard_40_wet_state_by_loaded_case").unwrap();
    for c in ["2.0", "5.0", "10.0"] {
        assert_eq!(py_str(gi(states, c).unwrap()), "DOES_NOT_CLOSE");
    }
    assert!(!pyjson::dumps(&gates, &Default::default()).unwrap().contains("\"PASS\""));
    // an admitted mission Xe load does not close the mass gate while no CBE exists
    let admitted = v5::MissionXeLoad::Admitted { loaded_kg: 2.0, source: "test".into() };
    let g2 = v5::mass_gates(&root(), &admitted).unwrap();
    assert_eq!(py_str(gi(&iter(&g2).unwrap()[1], "status").unwrap()), "INCOMPLETE_EVIDENCE");
    // a record outside the premises is MODEL_ERROR, never an evaluated gate
    let mut rec = record();
    set(line_mut(&mut rec, "AL-03"), "cbe_kg", Value::Float(0.9));
    assert!(v5::mass_gates_of(&rec, &root(), &v5::MissionXeLoad::NotAdmitted).is_err());
    let mut rec = record();
    if let Value::Dict(d) = &mut rec {
        if let Some(Value::List(r)) = d.get_mut("rollups") {
            set(&mut r[0], "all_terms_resolved", Value::Bool(true));
        }
    }
    assert!(v5::mass_gates_of(&rec, &root(), &v5::MissionXeLoad::NotAdmitted).is_err());
}

fn scratch(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("abep-mass-test-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(d.join(v5::LANE_REL)).unwrap();
    d
}

fn write_record(dir: &Path, rec: &Value) {
    std::fs::write(dir.join(v5::RECORD_REL), pyjson::dumps_config_file(rec).unwrap()).unwrap();
}

#[test]
fn wet_mass_not_evaluated_without_cbe() {
    let n = Value::Null;
    let o = wet_mass::wet_mass_pinned(&root(), &Value::str(rules::FLIGHT), &n, &n).unwrap();
    assert_eq!(py_str(gi(&o, "status").unwrap()), "NOT_EVALUATED");
    assert_eq!(gi(&o, "value").unwrap(), &Value::Null);
    assert_eq!(py_str(gi(&o, "wet_rollup_states").unwrap()), "['DOES_NOT_CLOSE']");
    let supplied = loads(r#"{"all_terms_resolved": false}"#).unwrap();
    let o = wet_mass::wet_mass(&root(), &Value::str(rules::FLIGHT), &n, &supplied).unwrap();
    assert_eq!(py_str(gi(&o, "status").unwrap()), "INCOMPLETE_EVIDENCE");
    let e = wet_mass::wet_mass(&root(), &Value::str("hall_c1_reference"), &n, &n).unwrap_err();
    assert_eq!(e.class, "RuntimeError");
    // an edited record: the parity entry reads it, the production entry refuses it by its sha256 (DIV-V03)
    let dir = scratch("cbe");
    let mut rec = record();
    set(line_mut(&mut rec, "AL-03"), "cbe_kg", Value::Float(1.0));
    write_record(&dir, &rec);
    assert_eq!(wet_mass::wet_mass(&dir, &Value::str(rules::FLIGHT), &n, &n).unwrap_err().class, "RuntimeError");
    assert_eq!(wet_mass::wet_mass_pinned(&dir, &Value::str(rules::FLIGHT), &n, &n).unwrap_err().class, "PinError");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn xe_sensitivity_cases_reproduce_the_committed_split() {
    let x = abep_subsystems::mass::py::load_json(&root(), "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json")
        .unwrap();
    let rows = iter(gi(gi(gi(&x, "design_cases").unwrap(), "loaded_split").unwrap(), "rows").unwrap()).unwrap();
    assert_eq!(rows.len(), 3);
    let items = iter(gi(&x, "items").unwrap()).unwrap();
    let item =
        |id: &str| gi(items.iter().find(|i| py_str(gi(i, "id").unwrap()) == id).unwrap(), "value").unwrap().clone();
    let (f_rsv, f_res) = (item("XV2-23"), item("XV2-24"));
    for row in rows {
        let c = gi(&row, "case_kg").unwrap();
        let sp = xe::case_split_loaded(c, &f_rsv, &f_res, &Value::str("LOADED")).unwrap();
        for k in ["mission_usable_kg", "reserve_kg", "residual_kg", "usable_incl_reserve_kg", "loaded_kg"] {
            assert_eq!(pyfmt::sig6(num(gi(&sp, k).unwrap()).unwrap()), num(gi(&row, k).unwrap()).unwrap(), "{k}");
        }
    }
    let e = xe::case_split_loaded(
        &Value::Float(2.0),
        &Value::Float(0.2),
        &Value::Float(0.02),
        &Value::str("USABLE_RESIDUAL_ON_TOP"),
    )
    .unwrap_err();
    assert_eq!(e.class, "BookingError");
}
