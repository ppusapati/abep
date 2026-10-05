//! `abep-provenance-verify [--root DIR] [--only NAME[,NAME...]] [--json]`
//!
//! Runs the generic provenance verifier (prereg_lock, audit_manifest, hallthruster_pin, h2_6_live_sources) on a
//! repository tree. Writes nothing. Exit 0: every check found nothing; 1: a finding; 2: usage error.

use abep_provenance::verifier::{run_checks, CheckName, CheckReport, H2_6_SPEC_SHA256};
use serde::Serialize;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Serialize)]
struct Output<'a> {
    schema: &'static str,
    root: String,
    h2_6_spec_sha256: &'static str,
    checks: &'a [CheckReport],
}

fn usage(msg: &str) -> ExitCode {
    eprintln!("{msg}\nusage: abep-provenance-verify [--root DIR] [--only NAME[,NAME...]] [--json]");
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let mut root = PathBuf::from(".");
    let mut checks: Vec<CheckName> = CheckName::ALL.to_vec();
    let mut json = false;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--root" => match args.next() {
                Some(r) => root = PathBuf::from(r),
                None => return usage("--root needs a directory"),
            },
            "--only" => {
                let Some(list) = args.next() else { return usage("--only needs check names") };
                let mut parsed = Vec::new();
                for name in list.split(',') {
                    match CheckName::parse(name) {
                        Some(c) => parsed.push(c),
                        None => return usage(&format!("unknown check {name:?}")),
                    }
                }
                checks = parsed;
            }
            "--json" => json = true,
            other => return usage(&format!("unknown argument {other:?}")),
        }
    }
    if !root.is_dir() {
        return usage(&format!("{} is not a directory", root.display()));
    }
    let reports = run_checks(&root, &checks);
    if json {
        let out = Output {
            schema: "abep_provenance_verifier_report_v1",
            root: root.display().to_string(),
            h2_6_spec_sha256: H2_6_SPEC_SHA256,
            checks: &reports,
        };
        match serde_json::to_string_pretty(&out) {
            Ok(s) => println!("{s}"),
            Err(e) => {
                eprintln!("cannot serialise the report: {e}");
                return ExitCode::from(2);
            }
        }
    } else {
        for r in &reports {
            println!("[{}] {}: {}", r.status, r.check, r.note);
            for f in &r.findings {
                println!("    - {} {} {}: {}", f.kind.as_str(), f.file, f.key, f.detail);
            }
        }
        let n_ok = reports.iter().filter(|r| r.verified()).count();
        println!("abep-provenance-verify: {n_ok}/{} verified", reports.len());
    }
    if reports.iter().all(CheckReport::verified) {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}
