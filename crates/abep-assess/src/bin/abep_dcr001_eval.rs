//! `abep-dcr001-eval search [--repo DIR] [--threads N] [--rust-commit SHA] --out SEARCH.json --spec-out SPEC.json`:
//! the DCR-DBF1-001 preregistered search (`docs/baseline/DCR-001/dcr001_eval_prereg_v1.json`) and the input of the
//! governed Python stability reference.
//!
//! `abep-dcr001-eval record [--repo DIR] [--threads N] --search REL --search-sha256 HEX --spec REL --spec-sha256 HEX
//! --python REL --python-sha256 HEX --out RECORD.json`: the evaluation record (R2 agreement of the Rust classes with the
//! Python reference on every row, selected-design detail under every coefficient set, DBF-1 comparison, cross-checks).
//! Exit 0 when the output is written, 4 when an input cannot be read or verified (fail closed), 2 on usage.

use abep_assess::dcr001::{diagnose, gather, record, search};
use std::collections::BTreeMap;
use std::path::PathBuf;

const USAGE: &str =
    "usage: abep-dcr001-eval search [--repo DIR] [--threads N] [--rust-commit SHA] --out FILE --spec-out \
FILE\n       abep-dcr001-eval record [--repo DIR] [--threads N] --search REL --search-sha256 HEX --spec REL \
--spec-sha256 HEX --python REL --python-sha256 HEX --out FILE";

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn usage() -> ! {
    eprintln!("{USAGE}");
    std::process::exit(2)
}

fn write(path: &str, v: &serde_json::Value) {
    let s = serde_json::to_string_pretty(v).unwrap_or_else(|e| fail(e));
    std::fs::write(path, s + "\n").unwrap_or_else(|e| fail(format!("{path}: {e}")));
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first().cloned() else { usage() };
    let mut opt: BTreeMap<String, String> = BTreeMap::new();
    let mut i = 1;
    while i < args.len() {
        let k = args[i].strip_prefix("--").unwrap_or_else(|| usage()).to_string();
        let v = args.get(i + 1).cloned().unwrap_or_else(|| usage());
        opt.insert(k, v);
        i += 2;
    }
    let repo = match opt.get("repo") {
        Some(r) => PathBuf::from(r),
        None => abep_provenance::workspace_repo_root().unwrap_or_else(|e| fail(e)),
    };
    let threads: usize = opt.get("threads").map(|t| t.parse().unwrap_or_else(|_| usage())).unwrap_or(3);
    let need = |k: &str| opt.get(k).cloned().unwrap_or_else(|| usage());
    let inp = gather(&repo).unwrap_or_else(|e| fail(e));
    match cmd.as_str() {
        "search" => {
            let commit = opt.get("rust-commit").cloned().unwrap_or_else(|| "UNRECORDED".into());
            let out = search(&inp, threads, &commit).unwrap_or_else(|e| fail(e));
            write(&need("out"), &out.record);
            write(&need("spec-out"), &out.spec);
        }
        "record" => {
            let r = record(
                &inp,
                &repo,
                &need("search"),
                &need("search-sha256"),
                &need("spec"),
                &need("spec-sha256"),
                &need("python"),
                &need("python-sha256"),
                threads,
            )
            .unwrap_or_else(|e| fail(e));
            write(&need("out"), &r);
        }
        "diagnose" => {
            let v = diagnose(&inp, threads).unwrap_or_else(|e| fail(e));
            write(&need("out"), &v);
        }
        _ => usage(),
    }
}
