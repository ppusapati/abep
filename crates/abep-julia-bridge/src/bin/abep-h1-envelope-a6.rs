//! `abep-h1-envelope-a6 <command> --kind study|grid [--root PATH]` (NP-HALL-PARAMETRIC-ENVELOPE addendum A6):
//! exit 0 ok, 1 refused, 2 usage.
//!
//!   generate --kind K                                write the A6 case file and launch manifest (grid: needs the study result)
//!   check --kind K                                   regenerate in memory: byte-equal to the committed files
//!   run-shard --kind K --shard I --out DIR           launch one shard (pinned Julia; sidecar)
//!   freeze --kind K --name NAME --out DIR FILE...    freeze shard outputs
//!   score-study --manifest M --manifest-sha256 H --rust-commit SHA --out DIR
//!                                                    score the study once: a6_convergence_study_result_v1.json / .md

use abep_julia_bridge::envelope_a6::{self as a6, Kind};
use abep_provenance::find_repo_root;
use abep_types::pyjson::{self, DumpOptions, Value};
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: abep-h1-envelope-a6 generate|check|run-shard|freeze|score-study --kind study|grid [...] [--root PATH]"
    );
    ExitCode::from(2)
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
    let kind = opt(&args, "--kind").and_then(|k| Kind::parse(&k));
    let result: Result<String, String> = match (cmd.as_str(), kind) {
        ("generate", Some(k)) => a6::write_generated(&root, k)
            .map(|()| "A6 case file and launch manifest written".into())
            .map_err(|e| e.to_string()),
        ("check", Some(k)) => {
            a6::check(&root, k).map(|n| format!("OK: {n} A6 cases reproduce byte for byte")).map_err(|e| e.to_string())
        }
        ("run-shard", Some(k)) => {
            let (Some(shard), Some(out)) =
                (opt(&args, "--shard").and_then(|s| s.parse::<usize>().ok()), opt(&args, "--out"))
            else {
                return usage();
            };
            a6::run_shard(&root, k, shard, &out)
                .map(|s| format!("A6 shard {shard} done; sidecar {:?}", s.output_sha256))
                .map_err(|e| e.to_string())
        }
        ("freeze", Some(k)) => {
            let (Some(name), Some(out)) = (opt(&args, "--name"), opt(&args, "--out")) else { return usage() };
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
            if files.is_empty() {
                return usage();
            }
            a6::freeze(&root, k, &name, &files, &PathBuf::from(out))
                .map(|(p, sha)| format!("frozen: {} sha256 {sha}", p.display()))
                .map_err(|e| e.to_string())
        }
        ("score-study", _) => {
            let (Some(m), Some(h), Some(c), Some(out)) = (
                opt(&args, "--manifest"),
                opt(&args, "--manifest-sha256"),
                opt(&args, "--rust-commit"),
                opt(&args, "--out"),
            ) else {
                return usage();
            };
            a6::score_study(&root, &PathBuf::from(m), &h, &c).map_err(|e| e.to_string()).and_then(|(v, md)| {
                let mut t = pyjson::dumps(&v, &DumpOptions::config_writer()).map_err(|e| format!("{e:?}"))?;
                t.push('\n');
                let dir = PathBuf::from(out);
                std::fs::write(dir.join("a6_convergence_study_result_v1.json"), t).map_err(|e| e.to_string())?;
                std::fs::write(dir.join("A6_CONVERGENCE_STUDY_RESULT.md"), md).map_err(|e| e.to_string())?;
                let o = v.as_dict().and_then(|d| d.get("outcome")).and_then(Value::as_str).unwrap_or("?").to_string();
                Ok(format!("A6 study outcome {o}"))
            })
        }
        _ => return usage(),
    };
    match result {
        Ok(m) => {
            println!("{m}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(1)
        }
    }
}
