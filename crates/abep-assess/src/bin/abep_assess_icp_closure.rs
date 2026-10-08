//! `abep-assess-icp-closure [--repo DIR] [--out FILE]`: the A9.38 P4 RF/ICP neutralizer closure record
//! (`docs/closure/icp/icp_closure_v1.json`, registration ICP-CLOSURE-REG-v1). Exit 0 when written (statuses are in the
//! record, fail closed), 4 when an input cannot be read or verified, 2 on usage.

use std::path::PathBuf;

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out) = (None, None);
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            _ => {
                eprintln!("usage: abep-assess-icp-closure [--repo DIR] [--out FILE]");
                std::process::exit(2);
            }
        }
        i += 2;
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().unwrap_or_else(|e| fail(e)));
    let v = abep_assess::closure_icp::build(&repo).unwrap_or_else(|e| fail(e));
    let text = abep_assess::closure_icp::render(&v).unwrap_or_else(|e| fail(e));
    match out {
        Some(p) => std::fs::write(&p, text).unwrap_or_else(|e| fail(format!("{}: {e}", p.display()))),
        None => print!("{text}"),
    }
}
