//! `abep-assess-matrix [--repo DIR] [--out FILE]`: the RFP constraint matrix (A9.31 sec. 17) on today's admitted raw
//! results of the repository; deterministic JSON. Exit 0 when the record is produced (its statuses are in the record,
//! fail closed), 4 when the configuration cannot be loaded.

use abep_assess::matrix::{constraint_matrix, to_json, RawPhysics};
use abep_assess::Thresholds;
use abep_config::ConfigPaths;
use std::path::PathBuf;

fn fail(e: abep_assess::AssessError) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut repo: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            _ => {
                eprintln!("usage: abep-assess-matrix [--repo DIR] [--out FILE]");
                std::process::exit(2);
            }
        }
        i += 2;
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let t = Thresholds::load(&ConfigPaths::from_env(&repo)).unwrap_or_else(|e| fail(e));
    let raw = RawPhysics::load_repository(&repo);
    let m = constraint_matrix(&t, &raw, &repo).unwrap_or_else(|e| fail(e));
    let text = to_json(&m).unwrap_or_else(|e| fail(e));
    match out {
        Some(p) => std::fs::write(p, text).expect("write output"),
        None => print!("{text}"),
    }
}
