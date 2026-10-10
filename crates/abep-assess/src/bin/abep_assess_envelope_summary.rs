//! `abep-assess-envelope-summary [--repo DIR] --envelope MANIFEST --envelope-sha256 HEX [--version v1|a6] [--out FILE]`: the compact
//! layer (a) summary of a frozen NP-HALL-PARAMETRIC-ENVELOPE envelope (PARAMETRIC / NOT_VALIDATED; no classification).
//! Exit 0 when written, 4 when an input cannot be read or verified, 2 on usage.

use abep_assess::closure::{ledger_bound, HallLimits};
use abep_assess::envelope_summary::summary;
use abep_assess::thresholds::Thresholds;
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use std::path::PathBuf;

fn fail(e: impl std::fmt::Display) -> ! {
    eprintln!("{e}");
    std::process::exit(4)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mut repo, mut out, mut env, mut sha) = (None, None, None, None);
    let mut a6 = false;
    let mut i = 0;
    while i < args.len() {
        match (args[i].as_str(), args.get(i + 1)) {
            ("--repo", Some(v)) => repo = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out = Some(PathBuf::from(v)),
            ("--envelope", Some(v)) => env = Some(PathBuf::from(v)),
            ("--envelope-sha256", Some(v)) => sha = Some(v.clone()),
            ("--version", Some(v)) if v == "v1" || v == "a6" => a6 = v == "a6",
            _ => {
                eprintln!("usage: abep-assess-envelope-summary [--repo DIR] --envelope MANIFEST --envelope-sha256 HEX [--out FILE]");
                std::process::exit(2);
            }
        }
        i += 2;
    }
    let (Some(env), Some(sha)) = (env, sha) else {
        eprintln!("--envelope and --envelope-sha256 are required");
        std::process::exit(2);
    };
    let repo = repo.unwrap_or_else(|| abep_provenance::workspace_repo_root().expect("repository root"));
    let e = if a6 {
        abep_hall::envelope::ingest_a6(&repo, &env, &sha)
    } else {
        abep_hall::envelope::ingest(&repo, &env, &sha)
    }
    .unwrap_or_else(|e| fail(e));
    let t = Thresholds::load(&abep_config::ConfigPaths::repository(&repo)).unwrap_or_else(|e| fail(e));
    let lim = |id: &str| t.limit(id).unwrap_or_else(|| fail(format!("threshold {id} not configured")));
    let lb = ledger_bound(&repo).unwrap_or_else(|e| fail(e));
    let limits = HallLimits {
        thrust_min_n: lim("HC-01"),
        thrust_capability_n: lim("HC-02"),
        p_bus_max_w: lim("HC-03"),
        p_non_hall_lb_w: lb.p_non_hall_lb_w,
    };
    let mut rec = summary(&e, &limits);
    if a6 {
        if let Value::Dict(d) = &mut rec {
            d.insert(
                "a6",
                Value::str("addendum A6 XE envelope (production-level numerics): INFO_T_GE_HC01_AT_PBUS and INFO_T_GE_HC02_AT_PBUS are the A6 point tests HALL_XE_T12_AT_PBUS and HALL_XE_T25_CAPABILITY_AT_PBUS; XE_FUNC is the v1 test and has no role for A6; the A3 overlay does not apply"),
            );
        }
        let mut text = pyjson::dumps(&rec, &DumpOptions::config_writer()).unwrap_or_else(|e| fail(format!("{e:?}")));
        text.push('\n');
        match out {
            Some(p) => std::fs::write(p, text).expect("write output"),
            None => print!("{text}"),
        }
        return;
    }
    let (a3, a3_sha) =
        abep_hall::envelope::a3_overlay(&repo, abep_hall::envelope::Family::Xe).unwrap_or_else(|e| fail(e));
    if let Value::Dict(d) = &mut rec {
        let mut n = Dict::new();
        n.insert("XE", Value::str(a3.as_str()));
        n.insert("result_sha256", a3_sha.map_or(Value::Null, Value::str));
        n.insert(
            "note",
            Value::str(if a3 == abep_hall::envelope::A3Overlay::NotAdequate {
                "XE point-test counts above are nominal raw counts; under A3_NOT_ADEQUATE every XE PASS / NOT_SUSTAINED point is NUMERICS_NOT_CONVERGED (unknown) for classification"
            } else {
                "XE counts follow the A3 outcome named here"
            }),
        );
        d.insert("numerics_a3", Value::Dict(n));
    }
    let mut text = pyjson::dumps(&rec, &DumpOptions::config_writer()).unwrap_or_else(|e| fail(format!("{e:?}")));
    text.push('\n');
    match out {
        Some(p) => std::fs::write(p, text).expect("write output"),
        None => print!("{text}"),
    }
}
