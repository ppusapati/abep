//! `abep-assess-parity [--repo DIR] eval <calls.json>`: evaluates registered parity calls and prints the results as
//! JSON (harness interface of the SC-WP-11 parity contracts).

use abep_assess::parity::{eval_calls, Ctx};
use abep_types::pyjson::{dumps, loads, DumpOptions};
use std::path::PathBuf;

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut repo: Option<PathBuf> = None;
    if args.first().map(String::as_str) == Some("--repo") && args.len() > 1 {
        repo = Some(PathBuf::from(args.remove(1)));
        args.remove(0);
    }
    if args.len() != 2 || args[0] != "eval" {
        eprintln!("usage: abep-assess-parity [--repo DIR] eval <calls.json>");
        std::process::exit(2);
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let text = std::fs::read_to_string(&args[1]).expect("calls file");
    let calls = loads(&text).expect("calls JSON");
    let ctx = Ctx::load(&repo).unwrap_or_else(|e| {
        eprintln!("{e}");
        std::process::exit(4)
    });
    let out = eval_calls(&ctx, &calls).unwrap_or_else(|e| {
        eprintln!("{e}");
        std::process::exit(4)
    });
    println!("{}", dumps(&out, &DumpOptions { ensure_ascii: false, ..Default::default() }).expect("serializable"));
}
