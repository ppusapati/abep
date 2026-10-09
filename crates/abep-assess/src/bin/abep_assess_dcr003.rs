//! `abep-assess-dcr003 [--repo DIR] [--out FILE] [--md FILE]`: the DCR-DBF1-003 evaluation (R-1 isolated co-located
//! match vs R-2 match at the RF generator) under `docs/baseline/DCR-003/dcr003_eval_prereg_v1.json`. The Rust commit
//! and tree state come from git. Exit 0 when the record is written (its statuses are in it, fail closed), 4 when an
//! input cannot be read or verified, 2 on usage.

use abep_assess::thermal_closure::dcr003::{markdown, run};
use abep_provenance::git::Git;
use abep_subsystems::thermal::RunContext;
use std::path::PathBuf;

const USAGE: &str = "usage: abep-assess-dcr003 [--repo DIR] [--out FILE] [--md FILE]";

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut md) = (None, None, None);
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
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
    let rec = run(&repo, RunContext { rust_commit: commit, rust_tree_dirty: dirty }).unwrap_or_else(|e| fail(e));
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
