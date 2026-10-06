//! The migration ledger equals the inventory row for row, the admitted rows and partial admissions are exactly those
//! recorded with their committed evidence, and a row cannot claim a status or an admission without recorded evidence.
//! The negative fixtures use rows / items that stay un-admitted (C-ABEP_SIM_COMPRESSOR_PY, NP-MISSION-INTEGRATION).

use abep_ci::ledger::{check, check_value, LEDGER_PATH};
use abep_provenance::workspace_repo_root;
use serde_json::{json, Value};

fn ledger() -> Value {
    let root = workspace_repo_root().unwrap();
    serde_json::from_slice(&std::fs::read(root.join(LEDGER_PATH)).unwrap()).unwrap()
}

fn row<'a>(l: &'a mut Value, id: &str) -> &'a mut Value {
    l["rows"].as_array_mut().unwrap().iter_mut().find(|r| r["id"] == id).unwrap()
}

fn violations(l: &Value) -> Vec<String> {
    check_value(&workspace_repo_root().unwrap(), l).unwrap().violations
}

#[test]
fn committed_ledger_is_consistent() {
    let r = check(&workspace_repo_root().unwrap()).expect("ledger and inventory load");
    assert!(r.violations.is_empty(), "{:#?}", r.violations);
    assert_eq!(r.rows, 227);
    assert_eq!((r.admitted_rows, r.admitted_partial, r.new_items_admitted), (13, 21, 1));
    let l = ledger();
    let k1 = l["rows"].as_array().unwrap().iter().find(|r| r["id"] == "C-ABEP_SIM_INTAKE_TPMC_PY").unwrap();
    assert_eq!(k1["status"], "PYTHON_REFERENCE");
    assert_eq!(
        k1["partial_admissions"][0]["admission_evidence"]["path"],
        "docs/performance/abep_core/parity_report_v2.json"
    );
}

#[test]
fn admission_without_evidence_is_refused() {
    let mut l = ledger();
    let r = row(&mut l, "C-ABEP_SIM_COMPRESSOR_PY");
    r["status_history"] = json!([{"from": "PYTHON_REFERENCE", "to": "ADMITTED", "date": "2026-10-05",
        "evidence": ["docs/rust_migration/CI_PLAN.md"], "history_entry": "test"}]);
    r["status"] = json!("ADMITTED");
    let v = violations(&l);
    assert!(v.iter().any(|s| s.contains("C-ABEP_SIM_COMPRESSOR_PY: ADMITTED without admission_evidence")), "{v:#?}");
    assert!(v.iter().any(|s| s.contains("C-ABEP_SIM_COMPRESSOR_PY: status ADMITTED needs a contract")));

    let r = row(&mut l, "C-ABEP_SIM_COMPRESSOR_PY");
    r["admission_evidence"] = json!({"path": "docs/rust_migration/contracts/NO_SUCH/parity_report_v1.json",
                                     "sha256": "0".repeat(64)});
    assert!(violations(&l).iter().any(|s| s.contains("admission_evidence") && s.contains("NO_SUCH")));

    let mut l = ledger();
    l["rows"][0]["admission_evidence"] = json!({"path": "Cargo.toml", "sha256": "0".repeat(64)});
    assert!(violations(&l).iter().any(|s| s.contains("admission_evidence recorded but status is")));

    let mut l = ledger();
    l["rows"].as_array_mut().unwrap().iter_mut().find(|r| r["id"] == "C-ABEP_SIM_INTAKE_TPMC_PY").unwrap()
        ["partial_admissions"][0]["admission_evidence"]["sha256"] = json!("0".repeat(64));
    assert!(violations(&l).iter().any(|s| s.contains("partial_admissions[0].admission_evidence")));
}

#[test]
fn status_changes_need_a_recorded_transition() {
    let mut l = ledger();
    row(&mut l, "C-ABEP_SIM_COMPRESSOR_PY")["status"] = json!("PREREG_PARITY");
    assert!(violations(&l).iter().any(|s| s.contains("without a recorded transition")));

    let mut l = ledger();
    let r = row(&mut l, "C-ABEP_SIM_COMPRESSOR_PY");
    r["status"] = json!("PREREG_PARITY");
    r["status_history"] = json!([{"from": "PYTHON_REFERENCE", "to": "PREREG_PARITY", "date": "2026-10-05",
        "evidence": ["docs/rust_migration/parity_contract_template_v3_1.json"], "history_entry": "test"}]);
    let tpl = "docs/rust_migration/parity_contract_template_v3_1.json";
    let sha = abep_provenance::sha256_file(&workspace_repo_root().unwrap().join(tpl)).unwrap();
    r["contract"] = json!({"path": tpl, "id": "TEST", "sha256": sha});
    let v = violations(&l);
    assert!(!v.iter().any(|s| s.starts_with("C-ABEP_SIM_COMPRESSOR_PY")), "{v:#?}");
    assert!(v.iter().any(|s| s.starts_with("summary.by_status")), "counts are recomputed");
}

#[test]
fn ids_classes_and_mirrored_fields_follow_the_inventory() {
    let mut l = ledger();
    l["rows"].as_array_mut().unwrap().pop();
    assert!(violations(&l).iter().any(|s| s.contains("row ids differ")));

    let mut l = ledger();
    l["rows"][3]["migration_class"] = json!("UNCLASSIFIED");
    let v = violations(&l);
    assert!(v.iter().any(|s| s.contains("not in the vocabulary")) && v.iter().any(|s| s.contains("!= inventory")));

    let mut l = ledger();
    l["rows"][3]["status"] = json!("SOMETHING");
    assert!(violations(&l).iter().any(|s| s.contains("status \"SOMETHING\" not in the vocabulary")));

    let mut l = ledger();
    l["new_items"][1]["status"] = json!("ADMITTED");
    assert!(violations(&l).iter().any(|s| s.contains("contract: needs path and sha256")));
}
