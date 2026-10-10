//! `abep-h1-envelope-cases <command> [--root PATH]` (NP-HALL-PARAMETRIC-ENVELOPE v1, A9.32): exit 0 ok, 1 refused, 2 usage.
//!
//!   generate                                         write the case file and launch manifest from the locked prereg
//!   check                                            regenerate in memory: byte-equal to the committed files, dry run
//!   run-shard --shard I --out DIR [--family F]       launch one shard (needs the pinned Julia; writes the sidecar)
//!   freeze --name NAME --out DIR FILE...             freeze shard outputs into <NAME>_raw.jsonl.gz + manifest

use abep_julia_bridge::envelope_cases::{self, N_SHARDS};
use abep_provenance::find_repo_root;
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: abep-h1-envelope-cases generate|check|run-shard --shard I --out DIR [--family XE|N2_PROXY|ALL]|freeze --name NAME --out DIR FILE... [--root PATH]"
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
    let result: Result<String, abep_types::AbepError> = match cmd.as_str() {
        "generate" => envelope_cases::write_generated(&root).map(|()| "case file and launch manifest written".into()),
        "check" => {
            envelope_cases::check(&root).map(|n| format!("OK: {n} cases reproduce byte for byte and pass the dry run"))
        }
        "run-shard" => {
            let (Some(shard), Some(out)) =
                (opt(&args, "--shard").and_then(|s| s.parse::<usize>().ok()), opt(&args, "--out"))
            else {
                return usage();
            };
            if shard >= N_SHARDS {
                return usage();
            }
            let family = opt(&args, "--family").unwrap_or_else(|| "ALL".into());
            envelope_cases::run_shard(&root, shard, &family, &out)
                .map(|s| format!("shard {shard} done; sidecar {:?}", s.output_sha256))
        }
        "freeze" => {
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
            envelope_cases::freeze(&root, &name, &files, &PathBuf::from(out))
                .map(|(p, sha)| format!("frozen: {} sha256 {sha}", p.display()))
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
