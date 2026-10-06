//! Parity CLI of abep-mission: reads `{"repo_root": ..., "requests": [...]}` as JSON on stdin and writes
//! `{"results": [...]}` on stdout (dispatcher and transport rules: `abep_mission::parity`).

use abep_mission::parity::{arg, decode, run_request, ParityContext};
use abep_types::pyjson::{dumps, loads, DumpOptions, Value};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

fn main() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let req = decode(loads(&input).expect("request JSON"));
    let repo = match arg(&req, "repo_root") {
        Value::Str(s) => PathBuf::from(s),
        _ => abep_provenance::find_repo_root(Path::new(".")).expect("repository root"),
    };
    let mut ctx = ParityContext::new(repo);
    let results: Vec<Value> =
        arg(&req, "requests").as_list().unwrap_or_default().iter().map(|r| run_request(&mut ctx, r)).collect();
    let out = abep_types::pydict! { "results" => results };
    let text = dumps(&out, &DumpOptions { ensure_ascii: false, ..Default::default() }).expect("serializable");
    std::io::stdout().write_all(text.as_bytes()).expect("stdout");
}
