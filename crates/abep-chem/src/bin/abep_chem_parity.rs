//! Parity runner of contract PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1: reads one JSON request from stdin and writes the
//! Rust results to stdout (`scripts/rust_migration/abep_chem_parity.py` drives it).
//!
//! Request: `{"tables": {"<id>": {"E": [...], "sigma": [...]}}, "calls": [{"id": "...", "op": "...", ...}]}`. Numbers
//! may be the strings "NaN", "Infinity", "-Infinity". A call names its representation by `"table": "<id>"` or gives
//! `"E"` and `"sigma"` inline. Ops: `maxwellian_rate` (te, tail), `tail_sensitivity` (eps), `step` (sigma0, e_th, te),
//! `write_table` (threshold, eps_max, tail, header_label, source), `render` (threshold, header_label, rows), `checked`
//! (te, tail, validity {kind: verified | unresolved | missing, max_mean_energy_ev}). `tail` is a string or null.
//!
//! Result per call: `{"id", "outcome": "value" | "python_exception" | "refused", "value" | "class" + "message" |
//! "status" + "message"}`, non-finite numbers as the strings above. Output is byte-deterministic (sorted keys).

use abep_chem::checked::{self, CrossSection, Validity};
use abep_chem::reference::{self, RefError, TailArg};
use abep_types::AbepError;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::io::{Read, Write};

fn num(v: &Value) -> Result<f64, String> {
    match v {
        Value::Number(n) => n.as_f64().ok_or_else(|| format!("{n} is not an f64")),
        Value::String(s) => match s.as_str() {
            "NaN" => Ok(f64::NAN),
            "Infinity" => Ok(f64::INFINITY),
            "-Infinity" => Ok(f64::NEG_INFINITY),
            _ => Err(format!("{s:?} is not a number")),
        },
        _ => Err(format!("{v} is not a number")),
    }
}

fn enc(x: f64) -> Value {
    if x.is_nan() {
        json!("NaN")
    } else if x.is_infinite() {
        json!(if x > 0.0 { "Infinity" } else { "-Infinity" })
    } else {
        json!(x)
    }
}

fn nums(v: &Value) -> Result<Vec<f64>, String> {
    v.as_array().ok_or_else(|| format!("{v} is not a list"))?.iter().map(num).collect()
}

fn field<'a>(call: &'a Value, k: &str) -> Result<&'a Value, String> {
    call.get(k).ok_or_else(|| format!("missing field {k}"))
}

fn tail_arg(call: &Value) -> Result<TailArg, String> {
    match field(call, "tail")? {
        Value::String(s) => Ok(TailArg::Str(s.clone())),
        Value::Null => Ok(TailArg::None),
        other => Err(format!("tail {other} is neither a string nor null")),
    }
}

type Table = (Vec<f64>, Vec<f64>);

fn named_table<'a>(id: &Value, tables: &'a BTreeMap<String, Table>) -> Result<(&'a [f64], &'a [f64]), String> {
    let id = id.as_str().ok_or("table must be a string")?;
    let (e, s) = tables.get(id).ok_or_else(|| format!("unknown table {id}"))?;
    Ok((e, s))
}

fn ok(v: Value) -> Map<String, Value> {
    let mut m = Map::new();
    m.insert("outcome".into(), json!("value"));
    m.insert("value".into(), v);
    m
}

fn failed(e: RefError) -> Map<String, Value> {
    let mut m = Map::new();
    match e {
        RefError::Python(p) => {
            m.insert("outcome".into(), json!("python_exception"));
            m.insert("class".into(), json!(p.class));
            m.insert("message".into(), json!(p.message));
        }
        RefError::Refused(a) => refused(&mut m, &a),
    }
    m
}

fn refused(m: &mut Map<String, Value>, a: &AbepError) {
    m.insert("outcome".into(), json!("refused"));
    m.insert("status".into(), json!(a.status().as_str()));
    m.insert("message".into(), json!(a.to_string()));
}

fn run(call: &Value, tables: &BTreeMap<String, Table>) -> Result<Map<String, Value>, String> {
    let op = field(call, "op")?.as_str().ok_or("op must be a string")?;
    let inline;
    let rep = if call.get("E").is_some() {
        inline = (nums(field(call, "E")?)?, nums(field(call, "sigma")?)?);
        Some((inline.0.as_slice(), inline.1.as_slice()))
    } else if let Some(id) = call.get("table") {
        Some(named_table(id, tables)?)
    } else {
        None
    };
    let need = || rep.ok_or_else(|| format!("{op} needs a representation"));
    Ok(match op {
        "maxwellian_rate" => {
            let (e, s) = need()?;
            let te = num(field(call, "te")?)?;
            match tail_arg(call)?.resolve().and_then(|t| reference::maxwellian_rate(e, s, te, t)) {
                Ok(k) => ok(enc(k)),
                Err(err) => failed(err),
            }
        }
        "tail_sensitivity" => {
            let (e, s) = need()?;
            let eps = nums(field(call, "eps")?)?;
            match reference::tail_sensitivity(e, s, &eps) {
                Ok(v) => ok(Value::Array(v.into_iter().map(|(a, b)| json!([enc(a), enc(b)])).collect())),
                Err(err) => failed(err),
            }
        }
        "step" => {
            let r = reference::step_cross_section_rate(
                num(field(call, "sigma0")?)?,
                num(field(call, "e_th")?)?,
                num(field(call, "te")?)?,
            );
            match r {
                Ok(k) => ok(enc(k)),
                Err(err) => failed(err),
            }
        }
        "write_table" => {
            let (e, s) = need()?;
            let label = field(call, "header_label")?.as_str().ok_or("header_label must be a string")?;
            let source = field(call, "source")?.as_str().ok_or("source must be a string")?;
            let r = reference::hallthruster_table(
                e,
                s,
                num(field(call, "threshold")?)?,
                num(field(call, "eps_max")?)?,
                &tail_arg(call)?,
                label,
                source,
            );
            match r {
                Ok(t) => ok(json!({
                    "rows": t.rows.iter().map(|&(a, b)| json!([enc(a), enc(b)])).collect::<Vec<_>>(),
                    "text": t.text,
                    "source_text": t.source_text,
                })),
                Err(err) => failed(err),
            }
        }
        "render" => {
            let label = field(call, "header_label")?.as_str().ok_or("header_label must be a string")?;
            let rows = field(call, "rows")?
                .as_array()
                .ok_or("rows must be a list")?
                .iter()
                .map(|r| {
                    let p = nums(r)?;
                    if p.len() == 2 {
                        Ok((p[0], p[1]))
                    } else {
                        Err("a row is [eps, k]".to_string())
                    }
                })
                .collect::<Result<Vec<_>, String>>()?;
            ok(json!(reference::render_hallthruster_table(num(field(call, "threshold")?)?, label, &rows)))
        }
        "checked" => {
            let (e, s) = need()?;
            let tail = match tail_arg(call)?.resolve() {
                Ok(t) => t,
                Err(err) => return Ok(failed(err)),
            };
            let v = field(call, "validity")?;
            let validity = match v.get("kind").and_then(Value::as_str) {
                Some("verified") => Validity::Verified { max_mean_energy_ev: num(field(v, "max_mean_energy_ev")?)? },
                Some("unresolved") => Validity::Unresolved,
                Some("missing") => Validity::MissingEntry,
                _ => return Err(format!("validity {v} has no known kind")),
            };
            let te = num(field(call, "te")?)?;
            match CrossSection::new(e.to_vec(), s.to_vec(), tail)
                .and_then(|xs| checked::maxwellian_rate(&xs, te, &validity))
            {
                Ok(r) => ok(enc(r.k_m3_s)),
                Err(a) => {
                    let mut m = Map::new();
                    refused(&mut m, &a);
                    m
                }
            }
        }
        other => return Err(format!("unknown op {other}")),
    })
}

fn main() {
    let mut input = String::new();
    if let Err(e) = std::io::stdin().read_to_string(&mut input) {
        eprintln!("abep-chem-parity: cannot read stdin: {e}");
        std::process::exit(2);
    }
    let request: Value = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("abep-chem-parity: request is not JSON: {e}");
            std::process::exit(2);
        }
    };
    let mut tables: BTreeMap<String, Table> = BTreeMap::new();
    if let Some(t) = request.get("tables").and_then(Value::as_object) {
        for (id, rep) in t {
            let parsed = (|| -> Result<Table, String> { Ok((nums(field(rep, "E")?)?, nums(field(rep, "sigma")?)?)) })();
            match parsed {
                Ok(p) => {
                    tables.insert(id.clone(), p);
                }
                Err(e) => {
                    eprintln!("abep-chem-parity: table {id}: {e}");
                    std::process::exit(2);
                }
            }
        }
    }
    let calls = request.get("calls").and_then(Value::as_array).cloned().unwrap_or_default();
    let mut results = Vec::with_capacity(calls.len());
    for call in &calls {
        let id = call.get("id").cloned().unwrap_or(Value::Null);
        let mut m = match run(call, &tables) {
            Ok(m) => m,
            Err(e) => {
                let mut m = Map::new();
                m.insert("outcome".into(), json!("invalid_request"));
                m.insert("message".into(), json!(e));
                m
            }
        };
        m.insert("id".into(), id);
        results.push(Value::Object(m));
    }
    let out = serde_json::to_string(&json!({ "results": results })).expect("serializable results");
    let mut stdout = std::io::stdout().lock();
    if stdout.write_all(out.as_bytes()).and_then(|_| stdout.write_all(b"\n")).is_err() {
        std::process::exit(2);
    }
}
