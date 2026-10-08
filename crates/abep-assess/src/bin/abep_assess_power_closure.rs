//! `abep-assess-power-closure [--repo DIR] [--out FILE] [--check]`: the A9.38 P6 power-closure record
//! (`docs/closure/power/power_ledger_v1.json` by default). `--check` compares with the committed file instead of
//! writing. Exit 0 when written / identical, 1 when stale, 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::power_closure::{power_closure_record, RECORD_REL};
use abep_assess::thresholds::Thresholds;
use abep_types::pyjson::dumps_config_file;
use std::path::PathBuf;

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut check) = (None, None, false);
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--check", _) => {
                check = true;
                i += 1;
                continue;
            }
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            _ => {
                eprintln!("usage: abep-assess-power-closure [--repo DIR] [--out FILE] [--check]");
                std::process::exit(2);
            }
        }
        i += 2;
    }
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let th = Thresholds::workspace().unwrap_or_else(|e| fail(e));
    let rec = power_closure_record(&repo, &th).unwrap_or_else(|e| fail(e));
    let bytes = dumps_config_file(&rec).unwrap_or_else(|e| fail(e));
    let out = out.unwrap_or_else(|| repo.join(RECORD_REL));
    if check {
        let same = std::fs::read(&out).map(|b| b == bytes).unwrap_or(false);
        if !same {
            eprintln!("STALE: {}", out.display());
            std::process::exit(1);
        }
        println!("OK {}", out.display());
        return;
    }
    std::fs::write(&out, &bytes).unwrap_or_else(|e| fail(e));
    println!("wrote {} sha256 {}", out.display(), abep_provenance::sha256_hex(&bytes));
}
