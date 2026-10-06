//! Parity-harness interface of the SC-WP-08 materials / life layer: `life_eval <calls.json>` evaluates every call
//! (`abep_subsystems::life::eval`) and prints the list of outcomes as JSON on stdout. A call may carry `"repeat": n`
//! (performance measurement): it is then evaluated n times and the result gains `"elapsed_s"`.

use abep_subsystems::life::eval::eval_call;
use abep_types::pyjson::{dumps, loads, read_text_utf8, DumpOptions, Value};
use std::time::Instant;

fn main() {
    let path = std::env::args().nth(1).expect("usage: life_eval <calls.json>");
    let bytes = std::fs::read(&path).expect("calls file");
    let calls = loads(&read_text_utf8(&bytes).expect("utf-8")).expect("calls JSON");
    let root = abep_provenance::workspace_repo_root().expect("repository root");
    let mut out = Vec::new();
    for call in calls.as_list().expect("a list of calls") {
        let repeat = call
            .as_dict()
            .and_then(|d| d.get("repeat"))
            .and_then(|v| match v {
                Value::Int(i) => i.as_i64(),
                _ => None,
            })
            .unwrap_or(1)
            .max(1);
        let t = Instant::now();
        let mut r = Value::Null;
        for _ in 0..repeat {
            r = eval_call(call, &root);
        }
        if repeat > 1 {
            if let Value::Dict(d) = &mut r {
                d.insert("elapsed_s", Value::Float(t.elapsed().as_secs_f64()));
            }
        }
        out.push(r);
    }
    let text = dumps(&Value::List(out), &DumpOptions { ensure_ascii: true, ..DumpOptions::default() }).expect("dump");
    println!("{text}");
}
