//! `abep-assess-closure [--repo DIR] [--envelope MANIFEST --envelope-sha256 HEX] [--rust-commit SHA] [--out FILE]`:
//! the decisive 196-state two-layer closure run and the A9.32 classification (NP-HALL-PARAMETRIC-ENVELOPE v1).
//! Without --envelope every layer (a) Hall field is NOT_EVALUATED (HALL_ENVELOPE_NOT_RUN). Exit 0 when the record is
//! produced (its statuses are in the record, fail closed), 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::closure::{closure_record, to_json};
use std::path::PathBuf;

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut env, mut env_sha, mut commit) = (None, None, None, None, String::new());
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            ("--envelope", Some(v)) => env = Some(PathBuf::from(v)),
            ("--envelope-sha256", Some(v)) => env_sha = Some(v.clone()),
            ("--rust-commit", Some(v)) => commit = v.clone(),
            _ => {
                eprintln!(
                    "usage: abep-assess-closure [--repo DIR] [--envelope MANIFEST --envelope-sha256 HEX] [--rust-commit SHA] [--out FILE]"
                );
                std::process::exit(2);
            }
        }
        i += 2;
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let envelope = match (env, env_sha) {
        (Some(p), Some(h)) => Some(abep_hall::envelope::ingest(&repo, &p, &h).unwrap_or_else(|e| fail(e))),
        (None, None) => None,
        _ => {
            eprintln!("--envelope and --envelope-sha256 go together (the frozen raw envelope is sha-pinned)");
            std::process::exit(2);
        }
    };
    let rec = closure_record(&repo, envelope.as_ref(), &commit).unwrap_or_else(|e| fail(e));
    let text = to_json(&rec).unwrap_or_else(|e| fail(e));
    match out {
        Some(p) => std::fs::write(p, text).expect("write output"),
        None => print!("{text}"),
    }
}
