//! CI replay of the captured Python reference of contract PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1 (scored ADMITTED, report
//! 4fc5611): every scored and domain / error call of the scoring request is re-run through `abep_chem::reference` and
//! compared with the captured Python outcome under the registered tolerances, and every registered representation
//! renders its frozen HallThruster table byte for byte (sha256 pinned by the contract). Lets CI check Rust against the
//! Python reference after Python is retired from active execution.

use abep_chem::reference::{self, RefError, TailArg};
use abep_provenance::{read_verified, workspace_repo_root};
use flate2::read::GzDecoder;
use serde_json::Value;
use std::collections::BTreeMap;
use std::io::Read;
use std::path::PathBuf;

const DIR: &str = "docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY";
const R_REL: f64 = 1e-13;
const A_ABS: f64 = 1e-250;
const SHARE_ABS: f64 = 4e-13;
/// Documented divergences (contract DIV-01 / DIV-02): Rust refuses where Python returns.
const DIVERGENT: [&str; 3] = ["DE-25", "DE-26", "DE-W7"];

fn root() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn captured(name: &str, manifest: &Value) -> Value {
    let sha = manifest["files"][name]["sha256"].as_str().unwrap();
    let gz = read_verified(&root().join(DIR).join("reference_outputs").join(name), sha).unwrap();
    let mut text = String::new();
    GzDecoder::new(gz.as_slice()).read_to_string(&mut text).unwrap();
    serde_json::from_str(&text).unwrap()
}

fn num(v: &Value) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().unwrap(),
        Value::String(s) => match s.as_str() {
            "NaN" => f64::NAN,
            "Infinity" => f64::INFINITY,
            "-Infinity" => f64::NEG_INFINITY,
            other => panic!("{other} is not a number"),
        },
        other => panic!("{other} is not a number"),
    }
}

fn nums(v: &Value) -> Vec<f64> {
    v.as_array().unwrap().iter().map(num).collect()
}

fn same(a: f64, b: f64) -> bool {
    a.to_bits() == b.to_bits() || (a.is_nan() && b.is_nan())
}

fn rate_ok(py: f64, rs: f64) -> bool {
    if !(py.is_finite() && rs.is_finite()) {
        return same(py, rs) || py == rs;
    }
    let d = (rs - py).abs();
    d <= R_REL * py.abs() || d <= A_ABS
}

fn tail_arg(v: &Value) -> TailArg {
    match v {
        Value::String(s) => TailArg::Str(s.clone()),
        _ => TailArg::None,
    }
}

/// The Rust outcome of one call: Ok(value as JSON-like) or the Python exception (class, message) or a refusal.
enum Out {
    Num(f64),
    Pairs(Vec<(f64, f64)>),
    Table(Vec<(f64, f64)>, String, Option<String>),
    Py(String, String),
    Refused,
}

fn out_of(r: Result<Out, RefError>) -> Out {
    match r {
        Ok(o) => o,
        Err(RefError::Python(p)) => Out::Py(p.class.to_string(), p.message),
        Err(RefError::Refused(_)) => Out::Refused,
    }
}

fn run(call: &Value, tables: &BTreeMap<String, (Vec<f64>, Vec<f64>)>) -> Option<Out> {
    let rep = || -> (Vec<f64>, Vec<f64>) {
        match call.get("table") {
            Some(t) => tables[t.as_str().unwrap()].clone(),
            None => (nums(&call["E"]), nums(&call["sigma"])),
        }
    };
    Some(match call["op"].as_str().unwrap() {
        "maxwellian_rate" => {
            let (e, s) = rep();
            out_of(
                tail_arg(&call["tail"])
                    .resolve()
                    .and_then(|t| reference::maxwellian_rate(&e, &s, num(&call["te"]), t))
                    .map(Out::Num),
            )
        }
        "tail_sensitivity" => {
            let (e, s) = rep();
            out_of(reference::tail_sensitivity(&e, &s, &nums(&call["eps"])).map(Out::Pairs))
        }
        "step" => out_of(
            reference::step_cross_section_rate(num(&call["sigma0"]), num(&call["e_th"]), num(&call["te"]))
                .map(Out::Num),
        ),
        "write_table" => {
            let (e, s) = rep();
            out_of(
                reference::hallthruster_table(
                    &e,
                    &s,
                    num(&call["threshold"]),
                    num(&call["eps_max"]),
                    &tail_arg(&call["tail"]),
                    call["header_label"].as_str().unwrap(),
                    call["source"].as_str().unwrap(),
                )
                .map(|t| Out::Table(t.rows, t.text, t.source_text)),
            )
        }
        _ => return None,
    })
}

fn check(id: &str, py: &Value, rs: &Out) -> Result<(), String> {
    let pairs =
        |v: &Value| -> Vec<(f64, f64)> { v.as_array().unwrap().iter().map(|p| (num(&p[0]), num(&p[1]))).collect() };
    match (py["outcome"].as_str().unwrap(), rs) {
        ("python_exception", Out::Py(c, m)) if py["class"] == c.as_str() && py["message"] == m.as_str() => Ok(()),
        ("value", Out::Num(k)) => rate_ok(num(&py["value"]), *k).then_some(()).ok_or(format!("{id}: {k}")),
        ("value", Out::Pairs(v)) => {
            let p = pairs(&py["value"]);
            let ok = p.len() == v.len()
                && p.iter().zip(v).all(|(a, b)| {
                    same(a.0, b.0) && if a.1.is_finite() { (a.1 - b.1).abs() <= SHARE_ABS } else { same(a.1, b.1) }
                });
            ok.then_some(()).ok_or(format!("{id}: tail shares differ"))
        }
        ("value", Out::Table(rows, text, src)) => {
            let p = pairs(&py["value"]["rows"]);
            let rows_ok = p.len() == rows.len() && p.iter().zip(rows).all(|(a, b)| same(a.0, b.0) && rate_ok(a.1, b.1));
            let text_ok = py["value"]["text"].as_str() == Some(text.as_str());
            let src_ok = py["value"]["source_text"].as_str() == src.as_deref();
            (rows_ok && text_ok && src_ok).then_some(()).ok_or(format!("{id}: table differs"))
        }
        _ => Err(format!("{id}: outcome differs ({})", py["outcome"])),
    }
}

/// Every scored and domain / error call of the scoring request (INV-04 / INV-06 helper calls excluded) against the
/// captured Python outcome; for the 37 registered tables (WT-TAB-xx) also the frozen file, byte for byte.
#[test]
fn rust_reproduces_the_captured_python_reference_and_the_frozen_tables() {
    let read_json = |rel: &str| -> Value { serde_json::from_slice(&std::fs::read(root().join(rel)).unwrap()).unwrap() };
    let contract = read_json(&format!("{DIR}/parity_prereg_v1.json"));
    let manifest = read_json(&format!("{DIR}/reference_outputs/MANIFEST.json"));
    let inputs = captured("inputs.json.gz", &manifest);
    let py = captured("python_outputs.json.gz", &manifest);
    let pins: BTreeMap<&str, &str> = contract["inputs"]["registered_tables"]["tables"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| (t["file"].as_str().unwrap(), t["sha256"].as_str().unwrap()))
        .collect();
    let frozen: BTreeMap<String, (&str, &str)> = inputs["registered_tables"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| {
            let file = r["file"].as_str().unwrap();
            (format!("WT-{}", r["id"].as_str().unwrap()), (file, pins[file]))
        })
        .collect();
    assert_eq!((frozen.len(), pins.len()), (37, 37));
    let request = &inputs["request"];
    let tables: BTreeMap<String, (Vec<f64>, Vec<f64>)> = request["tables"]
        .as_object()
        .unwrap()
        .iter()
        .map(|(k, v)| (k.clone(), (nums(&v["E"]), nums(&v["sigma"]))))
        .collect();
    let calls: Vec<&Value> = request["calls"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|c| {
            let id = c["id"].as_str().unwrap();
            py.get(id).is_some() && !id.starts_with("INV04-") && !id.starts_with("CKREF-")
        })
        .collect();
    let threads = std::thread::available_parallelism().map_or(4, |n| n.get());
    let (failures, n_frozen): (Vec<String>, usize) = std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|k| {
                let (calls, tables, py, frozen) = (&calls, &tables, &py, &frozen);
                s.spawn(move || {
                    let (mut bad, mut n_frozen) = (Vec::new(), 0);
                    for c in calls.iter().skip(k).step_by(threads) {
                        let id = c["id"].as_str().unwrap();
                        let Some(rs) = run(c, tables) else { continue };
                        if DIVERGENT.contains(&id) {
                            if !matches!(rs, Out::Refused) {
                                bad.push(format!("{id}: documented divergence not refused"));
                            }
                            continue;
                        }
                        if let Err(e) = check(id, &py[id], &rs) {
                            bad.push(e);
                        }
                        if let (Some((file, sha)), Out::Table(_, text, _)) = (frozen.get(id), &rs) {
                            let bytes = read_verified(&root().join(file), sha).unwrap();
                            n_frozen += 1;
                            if text.as_bytes() != bytes.as_slice() {
                                bad.push(format!("{id}: Rust text differs from the frozen {file}"));
                            }
                        }
                    }
                    (bad, n_frozen)
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).fold((Vec::new(), 0), |(mut b, n), (b2, n2)| {
            b.extend(b2);
            (b, n + n2)
        })
    });
    assert!(failures.is_empty(), "{failures:#?}");
    assert_eq!(n_frozen, 37, "every registered frozen table rendered");
    assert!(calls.len() > 3000, "replayed {} calls", calls.len());
}
