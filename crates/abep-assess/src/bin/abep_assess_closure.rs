//! `abep-assess-closure [--repo DIR] [--harness v1|v2] [--readiness] [--envelope MANIFEST --envelope-sha256 HEX]
//! [--run-label LABEL] [--rust-commit SHA] [--out FILE]`: the decisive 196-state two-layer closure run and the A9.32
//! classification (NP-HALL-PARAMETRIC-ENVELOPE v1; `--harness v2` is the addendum A2 harness consuming every required
//! physics path; `--readiness` prints the A2 M1 readiness listing). Without --envelope every layer (a) Hall field is
//! NOT_EVALUATED (HALL_ENVELOPE_NOT_RUN). Exit 0 when the record is produced (its statuses are in the record, fail
//! closed), 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::closure::{closure_record, to_json};
use abep_assess::closure_m1::record::{closure_record_v2, readiness_record};
use std::path::PathBuf;

const USAGE: &str = "usage: abep-assess-closure [--repo DIR] [--harness v1|v2] [--readiness] [--envelope MANIFEST \
--envelope-sha256 HEX] [--run-label LABEL] [--rust-commit SHA] [--out FILE]";

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn usage() -> ! {
    eprintln!("{USAGE}");
    std::process::exit(2)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut env, mut env_sha, mut commit) = (None, None, None, None, String::new());
    let (mut harness, mut ready, mut label) = ("v1".to_string(), false, "UNLABELLED".to_string());
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--readiness" {
            ready = true;
            i += 1;
            continue;
        }
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            ("--envelope", Some(v)) => env = Some(PathBuf::from(v)),
            ("--envelope-sha256", Some(v)) => env_sha = Some(v.clone()),
            ("--rust-commit", Some(v)) => commit = v.clone(),
            ("--harness", Some(v)) if v == "v1" || v == "v2" => harness = v.clone(),
            ("--run-label", Some(v)) => label = v.clone(),
            _ => usage(),
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
    let rec = if ready {
        readiness_record(&repo, envelope, &commit)
    } else if harness == "v2" {
        closure_record_v2(&repo, envelope, None, &commit, &label)
    } else {
        closure_record(&repo, envelope.as_ref(), &commit)
    }
    .unwrap_or_else(|e| fail(e));
    let text = to_json(&rec).unwrap_or_else(|e| fail(e));
    match out {
        Some(p) => std::fs::write(p, text).expect("write output"),
        None => print!("{text}"),
    }
}
