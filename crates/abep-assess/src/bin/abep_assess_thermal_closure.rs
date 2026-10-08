//! `abep-assess-thermal-closure [--repo DIR] [--inputs REL] [--out FILE] [--md FILE] [--dry-assemble]`: the P7 DBF-1
//! thermal closure (A9.38 priority 7) under `docs/closure/thermal/thermal_cases_prereg_v1.json`. `--inputs` names the
//! load-input version (default `docs/closure/thermal/thermal_load_inputs_v1.json`); `--dry-assemble` only assembles every
//! registered case (no solve) and prints the assembly reasons. The Rust commit and tree state come from git. Exit 0 when
//! the record is written (its statuses are in it, fail closed), 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::thermal_closure::record::{closure_record, dry_assemble, markdown};
use abep_assess::thermal_closure::Context;
use abep_provenance::git::Git;
use abep_subsystems::thermal::RunContext;
use std::path::PathBuf;

const USAGE: &str =
    "usage: abep-assess-thermal-closure [--repo DIR] [--inputs REL] [--out FILE] [--md FILE] [--dry-assemble]";

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut md, mut dry) = (None, None, None, false);
    let mut inputs = "docs/closure/thermal/thermal_load_inputs_v1.json".to_string();
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--dry-assemble" {
            dry = true;
            i += 1;
            continue;
        }
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--inputs", Some(v)) => inputs = v.clone(),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            ("--md", Some(v)) => md = Some(PathBuf::from(v)),
            _ => {
                eprintln!("{USAGE}");
                std::process::exit(2)
            }
        }
        i += 2;
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let git = Git::new(&repo);
    let commit = git.stdout(&["rev-parse", "--verify", "HEAD^{commit}"]).unwrap_or_else(|e| fail(e));
    let dirty = !git.stdout(&["status", "--porcelain", "--untracked-files=no"]).unwrap_or_else(|e| fail(e)).is_empty();
    let run = RunContext { rust_commit: commit, rust_tree_dirty: dirty };
    let ctx = Context::load(&repo, &inputs, run).unwrap_or_else(|e| fail(e));
    if dry {
        let r = dry_assemble(&ctx).unwrap_or_else(|e| fail(e));
        println!("{}", serde_json::to_string_pretty(&r).expect("json"));
        return;
    }
    let rec = closure_record(&ctx).unwrap_or_else(|e| fail(e));
    let mut text = serde_json::to_string_pretty(&rec).expect("json");
    text.push('\n');
    match out {
        Some(p) => std::fs::write(p, &text).expect("write output"),
        None => print!("{text}"),
    }
    if let Some(p) = md {
        std::fs::write(p, markdown(&rec)).expect("write markdown");
    }
}
