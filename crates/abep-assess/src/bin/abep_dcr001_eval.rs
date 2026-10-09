//! `abep-dcr001-eval search [--repo DIR] [--threads N] [--rust-commit SHA] --out SEARCH.json --spec-out SPEC.json`:
//! the DCR-DBF1-001 preregistered search (`docs/baseline/DCR-001/dcr001_eval_prereg_v1.json`) and the input of the
//! governed Python stability reference.
//!
//! `abep-dcr001-eval record [--repo DIR] [--threads N] --search REL --search-sha256 HEX --spec REL --spec-sha256 HEX
//! --python REL --python-sha256 HEX --out RECORD.json`: the evaluation record (R2 agreement of the Rust classes with the
//! Python reference on every row, selected-design detail under every coefficient set, DBF-1 comparison, cross-checks).
//! `abep-dcr001-eval window-search [--repo DIR] [--threads N] [--rust-commit SHA] --out SEARCH.json --spec-out SPEC.json`
//! and `abep-dcr001-eval window-record ... --out RECORD.json` (same pins as `record`): the amendment v3 (A9.39 item 3)
//! variable-effective-capture window search and record; `window-crosscheck --out FILE`: the v3 harness cross-checks.
//! Exit 0 when the output is written, 4 when an input cannot be read or verified (fail closed), 2 on usage.

use abep_assess::dcr001::{diagnose, gather, record, search};
use abep_assess::dcr001_window::{
    crosscheck_window, diag_design, gather_window, probe, window_record, window_search, WDesign, GOVERNING,
};
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
        "window-search" => {
            let w = gather_window(&repo, &inp).unwrap_or_else(|e| fail(e));
            let commit = opt.get("rust-commit").cloned().unwrap_or_else(|| "UNRECORDED".into());
            let out = window_search(&w, threads, &commit).unwrap_or_else(|e| fail(e));
            write(&need("out"), &out.record);
            write(&need("spec-out"), &out.spec);
        }
        "window-record" => {
            let w = gather_window(&repo, &inp).unwrap_or_else(|e| fail(e));
            let r = window_record(
                &w,
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
        "window-crosscheck" => {
            let w = gather_window(&repo, &inp).unwrap_or_else(|e| fail(e));
            write(&need("out"), &crosscheck_window(&w).unwrap_or_else(|e| fail(e)));
        }
        "window-diag" => {
            let w = gather_window(&repo, &inp).unwrap_or_else(|e| fail(e));
            let num = |k: &str| need(k).parse::<f64>().unwrap_or_else(|_| usage());
            let d = WDesign {
                g: num("g") as usize,
                filter: num("f") as usize,
                comp: num("c") as usize,
                a_max: num("amax"),
                n: num("n") as usize,
                target: num("j") as usize,
                o1: 0,
                o2: 0,
                log_width: 0.0,
                r_sus: 0.0,
                m_max: 0.0,
                d_max: 0.0,
                p_max: 0.0,
            };
            write(&need("out"), &diag_design(&w, &d, GOVERNING).unwrap_or_else(|e| fail(e)));
        }
        "window-probe" => {
            let w = gather_window(&repo, &inp).unwrap_or_else(|e| fail(e));
            let num = |k: &str| need(k).parse::<usize>().unwrap_or_else(|_| usage());
            let st = need("state");
            let i = inp.state_ids.iter().position(|x| *x == st).unwrap_or_else(|| usage());
            let v = probe(&w, num("g"), num("f"), num("c"), num("sc"), i).unwrap_or_else(|e| fail(e));
            write(&need("out"), &v);
        }
        "diagnose" => {
            let v = diagnose(&inp, threads).unwrap_or_else(|e| fail(e));
            write(&need("out"), &v);
        }
        _ => usage(),
    }
}
