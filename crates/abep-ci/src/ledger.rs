//! Migration ledger check (`docs/rust_migration/migration_state_v1.json`; programme_v3_1 lifecycle; SC-WP-12):
//! row ids equal the inventory ids, every class / status / disposition is in the inventory vocabulary, the mirrored
//! fields equal the inventory, a status differs from the inventory baseline only through a recorded transition with
//! existing evidence, and nothing claims ADMITTED without an admission-evidence file that exists and matches its sha256.

use abep_provenance::sha256_file;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::path::Path;

pub const LEDGER_PATH: &str = "docs/rust_migration/migration_state_v1.json";
pub const LEDGER_SCHEMA: &str = "abep_rust_migration_state_v1";
const MIRRORED: [&str; 6] = [
    "component",
    "migration_class",
    "classification_confidence",
    "classification_confidence_v3_1",
    "port_disposition",
    "simulation_completion_wp",
];
const ADMITTED_STATES: [&str; 2] = ["ADMITTED", "PYTHON_RETIRED_FROM_ACTIVE"];
const CONTRACT_STATES: [&str; 6] =
    ["PREREG_PARITY", "RUST_IMPL", "PARITY_PASS", "NOT_ADMITTED", "ADMITTED", "PYTHON_RETIRED_FROM_ACTIVE"];

#[derive(Debug, Clone)]
pub struct LedgerReport {
    pub rows: usize,
    pub admitted_rows: usize,
    pub admitted_partial: usize,
    pub new_items_admitted: usize,
    pub violations: Vec<String>,
}

fn load(root: &Path, rel: &str) -> Result<Value, String> {
    serde_json::from_slice(&std::fs::read(root.join(rel)).map_err(|e| format!("{rel}: {e}"))?)
        .map_err(|e| format!("{rel}: {e}"))
}

/// A `{path, sha256, ...}` record: the file exists and has the recorded sha256.
fn record_ok(root: &Path, v: &Value, what: &str, out: &mut Vec<String>) {
    let (Some(path), Some(want)) = (v.get("path").and_then(Value::as_str), v.get("sha256").and_then(Value::as_str))
    else {
        out.push(format!("{what}: needs path and sha256"));
        return;
    };
    match sha256_file(&root.join(path)) {
        Ok(got) if got == want => {}
        Ok(got) => out.push(format!("{what}: {path} sha256 {got} != recorded {want}")),
        Err(e) => out.push(format!("{what}: {e}")),
    }
}

fn strs(v: &Value) -> Vec<&str> {
    match v {
        Value::Array(a) => a.iter().filter_map(Value::as_str).collect(),
        Value::Object(o) => o.keys().map(String::as_str).collect(),
        _ => Vec::new(),
    }
}

fn counts<'a>(items: impl Iterator<Item = &'a str>) -> Value {
    let mut m: BTreeMap<&str, u64> = BTreeMap::new();
    for i in items {
        *m.entry(i).or_default() += 1;
    }
    json!(m)
}

/// Check the committed ledger of the repository at `root`.
pub fn check(root: &Path) -> Result<LedgerReport, String> {
    check_value(root, &load(root, LEDGER_PATH)?)
}

/// Check a ledger document; evidence paths resolve against `root`.
pub fn check_value(root: &Path, l: &Value) -> Result<LedgerReport, String> {
    let mut out = Vec::new();
    if l["schema"] != LEDGER_SCHEMA {
        out.push(format!("schema is not {LEDGER_SCHEMA}"));
    }
    for (i, g) in l["governing_records"].as_array().into_iter().flatten().enumerate() {
        record_ok(root, g, &format!("governing_records[{i}]"), &mut out);
    }
    record_ok(root, &l["inventory"], "inventory", &mut out);
    let inv_path = l["inventory"]["path"].as_str().ok_or("inventory.path missing")?;
    let inv = load(root, inv_path)?;
    let classes = strs(&inv["classification_vocabulary"]);
    let statuses = strs(&inv["status_vocabulary"]);
    let dispositions = strs(&inv["port_disposition_vocabulary"]);
    let kinds = strs(&l["authoritative_kind_vocabulary"]);
    let mapping = l["status_mapping_from_inventory"].as_object().cloned().unwrap_or_default();

    let inv_rows: Vec<&Value> = inv["components"]
        .as_array()
        .into_iter()
        .flatten()
        .chain(inv["non_py_execution_paths"].as_array().into_iter().flatten())
        .collect();
    let rows = l["rows"].as_array().ok_or("rows is not a list")?;
    let inv_ids: Vec<&str> = inv_rows.iter().filter_map(|r| r["id"].as_str()).collect();
    let ids: Vec<&str> = rows.iter().filter_map(|r| r["id"].as_str()).collect();
    if ids != inv_ids {
        out.push(format!(
            "row ids differ from the inventory ids ({} rows, {} inventory components)",
            ids.len(),
            inv_ids.len()
        ));
    }
    let (mut admitted_rows, mut admitted_partial) = (0, 0);
    for (r, ir) in rows.iter().zip(&inv_rows) {
        let id = r["id"].as_str().unwrap_or("?");
        for f in MIRRORED {
            if r[f] != ir[f] {
                out.push(format!("{id}: {f} {} != inventory {}", r[f], ir[f]));
            }
        }
        let class = r["migration_class"].as_str().unwrap_or("");
        let status = r["status"].as_str().unwrap_or("");
        let disposition = r["port_disposition"].as_str().unwrap_or("");
        if !classes.contains(&class) {
            out.push(format!("{id}: migration_class {class:?} not in the vocabulary"));
        }
        if !statuses.contains(&status) {
            out.push(format!("{id}: status {status:?} not in the vocabulary"));
        }
        if !dispositions.contains(&disposition) {
            out.push(format!("{id}: port_disposition {disposition:?} not in the vocabulary"));
        }
        // baseline status from the inventory, then the recorded transitions
        let inv_status = ir["status"].as_str().unwrap_or("");
        let (baseline, needs_partial) = if statuses.contains(&inv_status) {
            (inv_status.to_string(), false)
        } else if let Some(m) = mapping.get(inv_status) {
            (m["status"].as_str().unwrap_or("").to_string(), true)
        } else {
            out.push(format!("{id}: inventory status {inv_status:?} has no vocabulary entry or mapping"));
            (String::new(), false)
        };
        let history = r["status_history"].as_array().cloned().unwrap_or_default();
        let mut cur = baseline.clone();
        for (n, h) in history.iter().enumerate() {
            let (from, to) = (h["from"].as_str().unwrap_or(""), h["to"].as_str().unwrap_or(""));
            if from != cur || !statuses.contains(&to) {
                out.push(format!("{id}: status_history[{n}] {from} -> {to} does not continue from {cur}"));
            }
            let ev = strs(&h["evidence"]);
            if ev.is_empty() || h["history_entry"].as_str().is_none_or(str::is_empty) {
                out.push(format!("{id}: status_history[{n}] needs evidence paths and a history_entry"));
            }
            for p in ev {
                if !root.join(p).exists() {
                    out.push(format!("{id}: status_history[{n}] evidence {p} does not exist"));
                }
            }
            cur = to.to_string();
        }
        if cur != status {
            out.push(format!("{id}: status {status} without a recorded transition from {baseline}"));
        }
        // contract and admission evidence
        if r["contract"].is_null() {
            if CONTRACT_STATES.contains(&status) {
                out.push(format!("{id}: status {status} needs a contract"));
            }
        } else {
            record_ok(root, &r["contract"], &format!("{id}: contract"), &mut out);
        }
        if ADMITTED_STATES.contains(&status) {
            admitted_rows += 1;
            if r["admission_evidence"].is_null() {
                out.push(format!("{id}: {status} without admission_evidence"));
            } else {
                record_ok(root, &r["admission_evidence"], &format!("{id}: admission_evidence"), &mut out);
            }
        } else if !r["admission_evidence"].is_null() {
            out.push(format!("{id}: admission_evidence recorded but status is {status}"));
        }
        let partial = r["partial_admissions"].as_array().cloned().unwrap_or_default();
        for (n, p) in partial.iter().enumerate() {
            if p["status"] == "ADMITTED" {
                admitted_partial += 1;
                record_ok(root, &p["contract"], &format!("{id}: partial_admissions[{n}].contract"), &mut out);
                record_ok(
                    root,
                    &p["admission_evidence"],
                    &format!("{id}: partial_admissions[{n}].admission_evidence"),
                    &mut out,
                );
            }
        }
        if needs_partial && !partial.iter().any(|p| p["status"] == "ADMITTED") {
            out.push(format!("{id}: mapped inventory status needs an ADMITTED partial admission"));
        }
        // authoritative implementation
        let kind = r["authoritative_implementation"]["kind"].as_str().unwrap_or("");
        let kind_ok = match kind {
            "rust" => ADMITTED_STATES.contains(&status) || status == "RUST_BINDING_TO_RETIRE",
            "retired" => status == "FORMALLY_RETIRED_NOT_PORTED",
            "python" => !ADMITTED_STATES.contains(&status) && status != "FORMALLY_RETIRED_NOT_PORTED",
            _ => false,
        };
        if !kinds.contains(&kind) || !kind_ok {
            out.push(format!("{id}: authoritative_implementation.kind {kind:?} does not fit status {status}"));
        }
    }

    // new items (no Python reference)
    let new_vocab = strs(&l["new_item_status_vocabulary"]);
    let inv_new: Vec<&str> = inv["new_items_no_python_reference"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|n| n["id"].as_str())
        .collect();
    let new_items = l["new_items"].as_array().cloned().unwrap_or_default();
    if new_items.iter().filter_map(|n| n["id"].as_str()).collect::<Vec<_>>() != inv_new {
        out.push("new_items ids differ from the inventory new_items_no_python_reference".into());
    }
    let mut new_admitted = 0;
    for n in &new_items {
        let id = n["id"].as_str().unwrap_or("?");
        let st = n["status"].as_str().unwrap_or("");
        if !new_vocab.contains(&st) {
            out.push(format!("{id}: status {st:?} not in new_item_status_vocabulary"));
        }
        if st == "ADMITTED" {
            new_admitted += 1;
            record_ok(root, &n["contract"], &format!("{id}: contract"), &mut out);
            record_ok(root, &n["admission_evidence"], &format!("{id}: admission_evidence"), &mut out);
        } else if !n["admission_evidence"].is_null() {
            out.push(format!("{id}: admission_evidence recorded but status is {st}"));
        }
    }

    // summary recomputed from the rows
    fn s<'a>(rows: &'a [Value], k: &'static str) -> impl Iterator<Item = &'a str> {
        rows.iter().map(move |r| r[k].as_str().unwrap_or("none"))
    }
    let s = |k: &'static str| s(rows, k);
    let mut want = Map::new();
    want.insert("rows".into(), json!(rows.len()));
    want.insert("python_components".into(), json!(inv["components"].as_array().map_or(0, Vec::len)));
    want.insert("non_py_execution_paths".into(), json!(inv["non_py_execution_paths"].as_array().map_or(0, Vec::len)));
    want.insert("by_migration_class".into(), counts(s("migration_class")));
    want.insert("by_status".into(), counts(s("status")));
    want.insert("by_port_disposition".into(), counts(s("port_disposition")));
    want.insert("by_simulation_completion_wp".into(), counts(s("simulation_completion_wp")));
    want.insert(
        "by_authoritative_kind".into(),
        counts(rows.iter().map(|r| r["authoritative_implementation"]["kind"].as_str().unwrap_or(""))),
    );
    want.insert("rows_admitted".into(), json!(admitted_rows));
    want.insert("partial_admissions_admitted".into(), json!(admitted_partial));
    want.insert("rows_with_contract".into(), json!(rows.iter().filter(|r| !r["contract"].is_null()).count()));
    want.insert("new_items_by_status".into(), counts(new_items.iter().map(|n| n["status"].as_str().unwrap_or(""))));
    for (k, v) in &want {
        if &l["summary"][k] != v {
            out.push(format!("summary.{k} {} != recomputed {v}", l["summary"][k]));
        }
    }
    Ok(LedgerReport {
        rows: rows.len(),
        admitted_rows,
        admitted_partial,
        new_items_admitted: new_admitted,
        violations: out,
    })
}
