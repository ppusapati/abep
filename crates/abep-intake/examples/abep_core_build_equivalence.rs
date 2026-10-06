//! Runs the registered abep_core build-equivalence case set under the profile this example is built with and prints
//! `{"profile": ..., "total_sha256": ..., "cases": {id: sha256}}` as JSON on stdout.
//!
//! cargo run --example abep_core_build_equivalence [--release] -p abep-intake -- <profile label>

use abep_intake::build_equivalence::{load_cases, run_all, total_digest};
use std::process::ExitCode;

fn main() -> ExitCode {
    let label = std::env::args().nth(1).unwrap_or_else(|| "unlabelled".into());
    let root = match abep_provenance::workspace_repo_root() {
        Ok(r) => r,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let result = load_cases(&root).and_then(|file| run_all(&file));
    match result {
        Ok(digests) => {
            let cases: serde_json::Map<String, serde_json::Value> =
                digests.iter().map(|d| (d.id.clone(), serde_json::Value::String(d.sha256.clone()))).collect();
            let out = serde_json::json!({
                "profile": label,
                "debug_assertions": cfg!(debug_assertions),
                "n_cases": digests.len(),
                "total_sha256": total_digest(&digests),
                "cases": cases,
            });
            println!("{}", serde_json::to_string(&out).expect("serializable"));
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
