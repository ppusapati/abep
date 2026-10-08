//! `abep-assess-closure [--repo DIR] [--harness v1|v2] [--readiness] [--envelope MANIFEST --envelope-sha256 HEX]
//! [--run-label LABEL] [--rust-commit SHA] [--out FILE]`: the decisive 196-state two-layer closure run and the A9.32
//! classification (NP-HALL-PARAMETRIC-ENVELOPE v1; `--harness v2` is the addendum A2 harness consuming every required
//! physics path; `--readiness` prints the A2 M1 readiness listing; `--conservation-bounds` with `--harness v2` writes the
//! addendum A4 record `conservation_bounds_v1.json`; `--intake-closure` with `--harness v2` writes the addendum A5
//! record `intake_closure_a5_v1.json`; `--m2-dbf1 --feed-stability-reference FILE --feed-stability-sha256 HEX` with
//! `--harness v2` writes the addendum A8 M2 record of the DBF-1 design point). Without --envelope every layer (a) Hall field is
//! NOT_EVALUATED (HALL_ENVELOPE_NOT_RUN). Exit 0 when the record is produced (its statuses are in the record, fail
//! closed), 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::closure::{closure_record, to_json};
use abep_assess::closure_m1::conservation_record::conservation_bounds_record;
use abep_assess::closure_m1::dbf1_record::m2_dbf1_record;
use abep_assess::closure_m1::intake_record::intake_closure_record;
use abep_assess::closure_m1::record::{closure_record_v2_a6, readiness_record};
use std::path::PathBuf;

const USAGE: &str = "usage: abep-assess-closure [--repo DIR] [--harness v1|v2] [--readiness] [--conservation-bounds] [--intake-closure] \
[--m2-dbf1 --feed-stability-reference FILE --feed-stability-sha256 HEX] \
[--envelope MANIFEST --envelope-sha256 HEX] [--envelope-xe-a6 MANIFEST --envelope-xe-a6-sha256 HEX] [--run-label LABEL] [--rust-commit SHA] [--out FILE]";

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
    let (mut bounds, mut intake, mut m2) = (false, false, false);
    let (mut stab, mut stab_sha) = (None, None);
    let (mut a6, mut a6_sha) = (None, None);
    let mut i = 0;
    while i < args.len() {
        if ["--readiness", "--conservation-bounds", "--intake-closure", "--m2-dbf1"].contains(&args[i].as_str()) {
            m2 |= args[i] == "--m2-dbf1";
            ready |= args[i] == "--readiness";
            bounds |= args[i] == "--conservation-bounds";
            intake |= args[i] == "--intake-closure";
            i += 1;
            continue;
        }
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            ("--envelope", Some(v)) => env = Some(PathBuf::from(v)),
            ("--envelope-sha256", Some(v)) => env_sha = Some(v.clone()),
            ("--envelope-xe-a6", Some(v)) => a6 = Some(PathBuf::from(v)),
            ("--envelope-xe-a6-sha256", Some(v)) => a6_sha = Some(v.clone()),
            ("--rust-commit", Some(v)) => commit = v.clone(),
            ("--feed-stability-reference", Some(v)) => stab = Some(PathBuf::from(v)),
            ("--feed-stability-sha256", Some(v)) => stab_sha = Some(v.clone()),
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
    let xe_a6 = match (a6, a6_sha) {
        (Some(p), Some(h)) if harness == "v2" && !ready => {
            Some(abep_hall::envelope::ingest_a6(&repo, &p, &h).unwrap_or_else(|e| fail(e)))
        }
        (None, None) => None,
        _ => {
            eprintln!("--envelope-xe-a6 and --envelope-xe-a6-sha256 go together and need --harness v2 (addendum A6)");
            std::process::exit(2);
        }
    };
    if bounds && (harness != "v2" || ready || envelope.is_some()) {
        eprintln!("--conservation-bounds needs --harness v2, without --readiness or --envelope (A4 needs no envelope)");
        std::process::exit(2);
    }
    if intake && (harness != "v2" || ready || bounds || envelope.is_some()) {
        eprintln!("--intake-closure needs --harness v2, without --readiness, --conservation-bounds or --envelope");
        std::process::exit(2);
    }
    if m2 && (harness != "v2" || ready || bounds || intake || envelope.is_some() || xe_a6.is_some()) {
        eprintln!(
            "--m2-dbf1 needs --harness v2 and no other mode or envelope (addendum A8: no Hall envelope enters M2)"
        );
        std::process::exit(2);
    }
    if m2 != (stab.is_some() && stab_sha.is_some()) || stab.is_some() != stab_sha.is_some() {
        eprintln!(
            "--m2-dbf1 needs --feed-stability-reference FILE and --feed-stability-sha256 HEX (and only it uses them)"
        );
        std::process::exit(2);
    }
    let rec = if m2 {
        let p = stab.expect("checked");
        let rel = p.strip_prefix(&repo).map(PathBuf::from).unwrap_or(p);
        m2_dbf1_record(&repo, &rel, stab_sha.as_deref().expect("checked"), &commit, &label)
    } else if intake {
        intake_closure_record(&repo, &commit, &label)
    } else if bounds {
        conservation_bounds_record(&repo, &commit, &label)
    } else if ready {
        readiness_record(&repo, envelope, &commit)
    } else if harness == "v2" {
        closure_record_v2_a6(&repo, envelope, xe_a6, None, &commit, &label)
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
