//! `abep-h1-envelope-a3 <command> [--root PATH]` (NP-HALL-PARAMETRIC-ENVELOPE addendum A3, numerics adequacy):
//! exit 0 ok, 1 refused, 2 usage.
//!
//!   generate                                         write the A3 case file and launch manifest from the locked addendum
//!   check                                            regenerate in memory: byte-equal to the committed files
//!   run-shard --shard I --out DIR                    launch one A3 shard (needs the pinned Julia; writes the sidecar)
//!   freeze --name NAME --out DIR FILE...             freeze A3 shard outputs into <NAME>_raw.jsonl.gz + manifest
//!   score --manifest M --manifest-sha256 H --rust-commit SHA --out DIR
//!                                                    score once: a3_numerics_result_v1.json / A3_NUMERICS_RESULT.md
//!   determinism --manifest M --manifest-sha256 H --grid-manifest G --grid-sha256 GH
//!                                                    report-only: R0 records against the frozen grid records

use abep_julia_bridge::envelope_a3::{self, A3_SHARDS};
use abep_provenance::find_repo_root;
use abep_types::pyjson::{self, DumpOptions, Value};
use std::io::Read;
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: abep-h1-envelope-a3 generate|check|run-shard --shard I --out DIR|freeze --name NAME --out DIR FILE...|score --manifest M --manifest-sha256 H --rust-commit SHA --out DIR|determinism --manifest M --manifest-sha256 H --grid-manifest G --grid-sha256 GH [--root PATH]"
    );
    ExitCode::from(2)
}

fn grid_records(manifest: &str, sha: &str) -> Result<std::collections::BTreeMap<String, Value>, String> {
    let mp = PathBuf::from(manifest);
    let mb = abep_provenance::read_verified(&mp, sha).map_err(|e| e.to_string())?;
    let m = pyjson::loads(std::str::from_utf8(&mb).map_err(|e| e.to_string())?).map_err(|e| format!("{e:?}"))?;
    let raw = m.as_dict().and_then(|d| d.get("raw_file")).and_then(Value::as_str).ok_or("raw_file")?;
    let rsha = m.as_dict().and_then(|d| d.get("raw_sha256")).and_then(Value::as_str).ok_or("raw_sha256")?;
    let gz = abep_provenance::read_verified(&mp.parent().unwrap_or(std::path::Path::new(".")).join(raw), rsha)
        .map_err(|e| e.to_string())?;
    let mut text = String::new();
    flate2::read::GzDecoder::new(gz.as_slice()).read_to_string(&mut text).map_err(|e| e.to_string())?;
    let mut out = std::collections::BTreeMap::new();
    for l in text.lines().filter(|l| !l.trim().is_empty()) {
        let v = pyjson::loads(l).map_err(|e| format!("{e:?}"))?;
        let k = v.as_dict().and_then(|d| d.get("key")).and_then(Value::as_str).ok_or("key")?.to_string();
        out.insert(k, v);
    }
    Ok(out)
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
    let result: Result<String, String> = match cmd.as_str() {
        "generate" => envelope_a3::write_generated(&root)
            .map(|()| "A3 case file and launch manifest written".into())
            .map_err(|e| e.to_string()),
        "check" => envelope_a3::check(&root)
            .map(|n| format!("OK: {n} A3 cases reproduce byte for byte and pass the dry run"))
            .map_err(|e| e.to_string()),
        "run-shard" => {
            let (Some(shard), Some(out)) =
                (opt(&args, "--shard").and_then(|s| s.parse::<usize>().ok()), opt(&args, "--out"))
            else {
                return usage();
            };
            if shard >= A3_SHARDS {
                return usage();
            }
            envelope_a3::run_shard(&root, shard, &out)
                .map(|s| format!("A3 shard {shard} done; sidecar {:?}", s.output_sha256))
                .map_err(|e| e.to_string())
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
            envelope_a3::freeze(&root, &name, &files, &PathBuf::from(out))
                .map(|(p, sha)| format!("frozen: {} sha256 {sha}", p.display()))
                .map_err(|e| e.to_string())
        }
        "score" => {
            let (Some(m), Some(h), Some(c), Some(out)) = (
                opt(&args, "--manifest"),
                opt(&args, "--manifest-sha256"),
                opt(&args, "--rust-commit"),
                opt(&args, "--out"),
            ) else {
                return usage();
            };
            envelope_a3::score(&root, &PathBuf::from(m), &h, &c).map_err(|e| e.to_string()).and_then(|(v, md)| {
                let mut t = pyjson::dumps(&v, &DumpOptions::config_writer()).map_err(|e| format!("{e:?}"))?;
                t.push('\n');
                let dir = PathBuf::from(out);
                std::fs::write(dir.join("a3_numerics_result_v1.json"), t).map_err(|e| e.to_string())?;
                std::fs::write(dir.join("A3_NUMERICS_RESULT.md"), md).map_err(|e| e.to_string())?;
                let o = v.as_dict().and_then(|d| d.get("outcome")).and_then(Value::as_str).unwrap_or("?").to_string();
                Ok(format!("A3 outcome {o}"))
            })
        }
        "determinism" => {
            let (Some(m), Some(h), Some(g), Some(gh)) = (
                opt(&args, "--manifest"),
                opt(&args, "--manifest-sha256"),
                opt(&args, "--grid-manifest"),
                opt(&args, "--grid-sha256"),
            ) else {
                return usage();
            };
            envelope_a3::read_frozen(&root, &PathBuf::from(m), &h).map_err(|e| e.to_string()).and_then(|(a3, _)| {
                let grid = grid_records(&g, &gh)?;
                let rows = envelope_a3::determinism(&a3, &grid);
                let n_same = rows.iter().filter(|r| r.1).count();
                let mut s =
                    format!("determinism (report only): {n_same} / {} R0 records identical to the grid\n", rows.len());
                for (k, same, diff) in rows {
                    s.push_str(&format!("{} {k} {diff}\n", if same { "SAME" } else { "DIFF" }));
                }
                Ok(s)
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
