//! `abep-h1-envelope-a7 <command> [--kind demo-rp1|demo-rest|stage1|stage2] [--root PATH]` (NP-HALL-PARAMETRIC-ENVELOPE addendum A7):
//! exit 0 ok, 1 refused, 2 usage.
//!
//!   keys                                             print the demonstration keys computed from the frozen inputs
//!   generate --kind K                                write the A7 case file and launch manifest (stage1: needs the RP-1
//!                                                    demonstration result, stage2: the full one, each demonstrated)
//!   check --kind K                                   regenerate in memory: byte-equal to the committed files
//!   run-shard --kind K --shard I --out DIR           launch one shard (pinned Julia; sidecar)
//!   freeze --kind K --name NAME --out DIR FILE...    freeze shard outputs
//!   score-demo --scope rp1|all --manifest-rp1 M --manifest-rp1-sha256 H [--manifest-rest M --manifest-rest-sha256 H]
//!              --rust-commit SHA --out DIR           score the demonstration of the scope once (result JSON + page)

use abep_julia_bridge::envelope_a7::{self as a7, Kind, Scope};
use abep_provenance::find_repo_root;
use abep_types::pyjson::{self, DumpOptions, Value};
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: abep-h1-envelope-a7 keys|generate|check|run-shard|freeze|score-demo [--kind demo-rp1|demo-rest|stage1|stage2] [...] [--root PATH]"
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
        ("keys", _) => a7::demo_keys(&root)
            .map(|dk| {
                let mut s = String::new();
                for (title, v) in
                    [("A6 study keys", &dk.a6), ("fresh seeded keys", &dk.fresh), ("RP-1 seeded keys", &dk.rp1)]
                {
                    s.push_str(&format!("{title}:\n"));
                    for k in v {
                        s.push_str(&format!("  {k}\n"));
                    }
                }
                s
            })
            .map_err(|e| e.to_string()),
        ("generate", Some(k)) => a7::write_generated(&root, k)
            .map(|()| "A7 case file and launch manifest written".into())
            .map_err(|e| e.to_string()),
        ("check", Some(k)) => {
            a7::check(&root, k).map(|n| format!("OK: {n} A7 cases reproduce byte for byte")).map_err(|e| e.to_string())
        }
        ("run-shard", Some(k)) => {
            let (Some(shard), Some(out)) =
                (opt(&args, "--shard").and_then(|s| s.parse::<usize>().ok()), opt(&args, "--out"))
            else {
                return usage();
            };
            a7::run_shard(&root, k, shard, &out)
                .map(|s| format!("A7 shard {shard} done; sidecar {:?}", s.output_sha256))
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
            a7::freeze(&root, k, &name, &files, &PathBuf::from(out))
                .map(|(p, sha)| format!("frozen: {} sha256 {sha}", p.display()))
                .map_err(|e| e.to_string())
        }
        ("score-demo", _) => {
            let scope = match opt(&args, "--scope").as_deref() {
                Some("rp1") => Scope::Rp1,
                Some("all") => Scope::All,
                _ => return usage(),
            };
            let (Some(m1), Some(h1), Some(c), Some(out)) = (
                opt(&args, "--manifest-rp1"),
                opt(&args, "--manifest-rp1-sha256"),
                opt(&args, "--rust-commit"),
                opt(&args, "--out"),
            ) else {
                return usage();
            };
            let mut frozen = vec![(PathBuf::from(m1), h1)];
            if scope == Scope::All {
                let (Some(m2), Some(h2)) = (opt(&args, "--manifest-rest"), opt(&args, "--manifest-rest-sha256")) else {
                    return usage();
                };
                frozen.push((PathBuf::from(m2), h2));
            }
            let refs: Vec<(&std::path::Path, &str)> = frozen.iter().map(|(p, h)| (p.as_path(), h.as_str())).collect();
            a7::score_demo(&root, scope, &refs, &c).map_err(|e| e.to_string()).and_then(|(v, md)| {
                let mut t = pyjson::dumps(&v, &DumpOptions::config_writer()).map_err(|e| format!("{e:?}"))?;
                t.push('\n');
                let dir = PathBuf::from(out);
                let jname = scope.result_rel().rsplit('/').next().unwrap_or("result.json");
                std::fs::write(dir.join(jname), t).map_err(|e| e.to_string())?;
                std::fs::write(dir.join(scope.page_name()), md).map_err(|e| e.to_string())?;
                let o = v.as_dict().and_then(|d| d.get("outcome")).and_then(Value::as_str).unwrap_or("?").to_string();
                Ok(format!("A7 demonstration outcome {o}"))
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
