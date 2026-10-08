//! `abep-air-cases <command> [--root PATH]` (NP-HALL-CHEM-AIR, A9.33 Q2): exit 0 ok, 1 refused, 2 usage.
//!
//!   audit-generate                                       write the CA-HALL-AIR-v1 audit case file and snapshot MANIFEST
//!   audit-check                                          regenerate in memory: byte-equal to the committed files
//!   audit-freeze --name NAME --out DIR FILE...           freeze audit shard outputs (sorted gzip JSONL + sha manifest)
//!   audit-verdicts --manifest M --manifest-sha256 H --out F   verdicts from a frozen record file only

use abep_julia_bridge::{air_audit, air_cases};
use abep_provenance::find_repo_root;
use abep_types::pyjson::{self, DumpOptions};
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: abep-air-cases audit-generate|audit-check|audit-freeze --name NAME --out DIR FILE...|audit-verdicts --manifest M --manifest-sha256 H --out F [--root PATH]"
    );
    ExitCode::from(2)
}

/// Positional arguments after the command, skipping `--flag value` pairs.
fn positional(args: &[String]) -> Vec<PathBuf> {
    let mut files = Vec::new();
    let mut skip = false;
    for a in &args[1..] {
        if skip {
            skip = false;
            continue;
        }
        if a.starts_with("--") {
            skip = true;
            continue;
        }
        files.push(PathBuf::from(a));
    }
    files
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first().cloned() else { return usage() };
    let root = match opt(&args, "--root") {
        Some(r) => PathBuf::from(r),
        None => match std::env::current_dir()
            .map_err(|e| e.to_string())
            .and_then(|d| find_repo_root(&d).map_err(|e| e.to_string()))
        {
            Ok(r) => r,
            Err(e) => {
                eprintln!("repository root: {e}");
                return ExitCode::from(1);
            }
        },
    };
    let result: Result<String, abep_types::AbepError> = match cmd.as_str() {
        "audit-generate" => air_cases::write_audit(&root).map(|()| "audit case file and MANIFEST written".into()),
        "audit-check" => air_cases::check_audit(&root).map(|n| format!("OK: {n} audit cases reproduce byte for byte")),
        "audit-freeze" => {
            let (Some(name), Some(out)) = (opt(&args, "--name"), opt(&args, "--out")) else { return usage() };
            let files = positional(&args);
            if files.is_empty() {
                return usage();
            }
            air_cases::freeze_audit(&root, &name, &files, &PathBuf::from(out))
                .map(|(p, sha)| format!("frozen: {} sha256 {sha}", p.display()))
        }
        "audit-verdicts" => {
            let (Some(m), Some(h), Some(out)) =
                (opt(&args, "--manifest"), opt(&args, "--manifest-sha256"), opt(&args, "--out"))
            else {
                return usage();
            };
            air_audit::read_frozen(&root, &PathBuf::from(m), &h)
                .and_then(|recs| air_audit::verdicts(&root, &recs))
                .and_then(|v| {
                    let mut t = pyjson::dumps(&v, &DumpOptions::config_writer())
                        .map_err(|e| abep_types::AbepError::Model { message: e.to_string() })?;
                    t.push('\n');
                    std::fs::write(&out, t)
                        .map_err(|e| abep_types::AbepError::Io { path: out.clone(), message: e.to_string() })?;
                    Ok(format!("verdicts written: {out}"))
                })
        }
        _ => return usage(),
    };
    match result {
        Ok(msg) => {
            println!("{msg}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("refused ({:?}): {e}", e.status());
            ExitCode::from(1)
        }
    }
}
