//! The NI-ABEP-CLI acceptance run (acceptance_v2 `decision_rules.once`): executes every registered case against a
//! built `abep` binary on a clean committed tree and writes acceptance_report_v2.json / .md.
//!
//! ```text
//! cargo run --locked -q -p abep-cli --example cli_acceptance -- --abep target/debug/abep --work <scratch dir> \
//!     [--profile dev] [--report-dir docs/rust_migration/contracts/NI-ABEP-CLI]
//! ```
//!
//! `--development` runs the same cases on a possibly dirty tree and prints the body; it never writes the report.
//!
//! Exit 0 on ACCEPTED, 1 on NOT_ACCEPTED / NOT_RUN_INPUT_MISMATCH, 2 on a usage or runner error.

use abep_cli::acceptance::{self, Config, Mode, PREREG_REL};
use abep_provenance::{find_repo_root, sha256_hex};
use serde_json::{json, Value};
use std::path::PathBuf;
use std::process::{Command, ExitCode};

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

/// UTC time stamp `YYYY-MM-DDTHH:MM:SSZ` (civil-from-days, proleptic Gregorian).
fn utc_now() -> String {
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_secs()) as i64;
    let (days, rem) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    format!("{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, rem % 3600 / 60, rem % 60)
}

fn md(report: &Value) -> String {
    let s = |v: &Value| v.as_str().map_or_else(|| v.to_string(), str::to_string);
    let mut l = vec![
        format!("# abep CLI acceptance v2: {}", s(&report["verdict"])),
        String::new(),
        format!(
            "Generated from `acceptance_report_v2.json` (do not edit). Preregistration `{}` (sha256 `{}`).",
            s(&report["prereg"]["path"]),
            s(&report["prereg"]["sha256"])
        ),
        String::new(),
        format!(
            "* Run: {} at `{}` (tracked tree dirty: {}), {}, binary `{}` ({} profile, sha256 `{}`).",
            s(&report["provenance"]["utc"]),
            s(&report["provenance"]["git_head"]),
            report["provenance"]["git_dirty"],
            s(&report["provenance"]["rustc"]),
            s(&report["provenance"]["abep_binary"]["name"]),
            s(&report["provenance"]["abep_binary"]["profile"]),
            s(&report["provenance"]["abep_binary"]["sha256"])
        ),
        format!(
            "* Cases: {} ; meeting expectation {} ; process runs {}.",
            report["counts"]["cases"], report["counts"]["cases_meeting_expectation"], report["counts"]["runs"]
        ),
        format!(
            "* Determinism: DET-RUN {} / DET-THREADS {} command cases hold; DET-ENV-CRATE {}.",
            report["determinism"]["DET-RUN"].as_array().map_or(0, |a| a.iter().filter(|x| x["holds"] == true).count()),
            report["determinism"]["DET-THREADS"]
                .as_array()
                .map_or(0, |a| a.iter().filter(|x| x["holds"] == true).count()),
            report["determinism"]["DET-ENV-CRATE"]["holds"]
        ),
        format!(
            "* Static: STATIC-DEP {} ({}); STATIC-NOPY {}.",
            report["static"]["STATIC-DEP"]["holds"],
            s(&report["static"]["STATIC-DEP"]["note"]),
            report["static"]["STATIC-NOPY"]["holds"]
        ),
        String::new(),
        "| case | argv | expected (status / exit / reason) | runs: exit, status, reason | meets |".into(),
        "|---|---|---|---|---|".into(),
    ];
    for c in report["cases"].as_array().into_iter().flatten() {
        let e = &c["expected"];
        let runs: Vec<String> = c["runs"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|r| format!("{} {} {} {}", s(&r["run"]), r["exit"], s(&r["status"]), s(&r["reason_code"])))
            .collect();
        let argv: Vec<String> = c["argv"].as_array().into_iter().flatten().map(s).collect();
        l.push(format!(
            "| {} | `{}` | {} / {} / {} | {} | {} |",
            s(&c["id"]),
            argv.join(" "),
            s(&e["status"]),
            e["exit"],
            s(&e["reason_code"]),
            runs.join("; "),
            if c["meets_expectation"] == true { "yes" } else { "NO" }
        ));
    }
    l.push(String::new());
    if let Some(p) = report["problems"].as_array().filter(|p| !p.is_empty()) {
        l.push("Problems:".into());
        l.push(String::new());
        for x in p {
            l.push(format!("* {}", s(x)));
        }
        l.push(String::new());
    }
    l.push(format!("Ledger update requested: {}", s(&report["ledger_update_requested"]["text"])));
    l.push(String::new());
    l.join("\n")
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (Some(abep), Some(work)) = (opt(&args, "--abep"), opt(&args, "--work")) else {
        eprintln!("usage: cli_acceptance --abep PATH --work DIR [--profile NAME] [--report-dir DIR | --development]");
        return ExitCode::from(2);
    };
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let repo = match find_repo_root(&cwd) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::from(2);
        }
    };
    let abep = std::fs::canonicalize(&abep).unwrap_or_else(|_| PathBuf::from(&abep));
    // --development: the same cases on a possibly dirty tree, printed only (never a report).
    let development = args.iter().any(|a| a == "--development");
    if development && opt(&args, "--report-dir").is_some() {
        eprintln!("--development never writes the report");
        return ExitCode::from(2);
    }
    let mode = if development { Mode::Development } else { Mode::Acceptance };
    let cfg = Config { repo: repo.clone(), abep: abep.clone(), work: PathBuf::from(&work), mode };
    let (body, problems) = match acceptance::run(&cfg) {
        Ok(x) => x,
        Err(e) => {
            eprintln!("runner error: {e}");
            return ExitCode::from(2);
        }
    };
    let prereg_sha = std::fs::read(repo.join(PREREG_REL)).map(|b| sha256_hex(&b)).unwrap_or_default();
    let rustc = Command::new("rustc")
        .arg("--version")
        .output()
        .map_or_else(|_| String::new(), |o| String::from_utf8_lossy(&o.stdout).trim().to_string());
    let verdict = body["verdict"].clone();
    let accepted = verdict == "ACCEPTED";
    let mut report = json!({
        "schema": "abep_new_infrastructure_acceptance_report_v1",
        "id": "ACCEPT-NI-ABEP-CLI-V2-REPORT",
        "item": "NI-ABEP-CLI",
        "simulation_completion_wp": "SC-WP-13",
        "prereg": {"id": "ACCEPT-NI-ABEP-CLI-V2", "path": PREREG_REL, "sha256": prereg_sha},
        "provenance": {
            "utc": utc_now(),
            "git_head": body["git_head"],
            "git_dirty": body["git_dirty"],
            "rustc": rustc,
            "abep_binary": {
                "name": abep.file_name().map(|n| n.to_string_lossy().into_owned()),
                "profile": opt(&args, "--profile").unwrap_or_else(|| "dev".into()),
                "sha256": std::fs::read(&abep).map(|b| sha256_hex(&b)).ok(),
            },
            "source_sha256": acceptance::source_sha256(&repo),
            "commands": [
                "cargo build --locked -p abep-cli (CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0)",
                "cargo run --locked -q -p abep-cli --example cli_acceptance -- --abep target/debug/abep --work <scratch> --report-dir docs/rust_migration/contracts/NI-ABEP-CLI"
            ],
        },
        "decision_rules_applied": [
            "per_case: every run meets EXIT, STATUS, PAYLOAD, FILES, PROV and NO_VERDICT",
            "determinism: DET-RUN and DET-THREADS for every command case, DET-ENV-CRATE",
            "static: STATIC-DEP, STATIC-NOPY",
            "verdict: ACCEPTED iff all hold"
        ],
        "verdict": verdict,
        "problems": problems,
        "ledger_update_requested": {
            "item": "NI-ABEP-CLI",
            "to": if accepted { "ACCEPTED" } else { "RUST_IMPL" },
            "contract": {"path": PREREG_REL, "id": "ACCEPT-NI-ABEP-CLI-V2", "sha256": prereg_sha},
            "admission_evidence": if accepted { Value::from("docs/rust_migration/contracts/NI-ABEP-CLI/acceptance_report_v2.json") } else { Value::Null },
            "implementation": ["crates/abep-cli"],
            "text": if accepted {
                "NI-ABEP-CLI -> ACCEPTED in docs/rust_migration/migration_state_v1.json (evidence: this report); ADMITTED after the CI determinism job (CI_PLAN § 5) lands"
            } else {
                "NI-ABEP-CLI -> RUST_IMPL (acceptance v2 NOT_ACCEPTED; a code fix plus acceptance_v3 is needed)"
            },
        },
        "what_this_is_not": [
            "not physics and not a gate verdict: the CLI never relabels a crate status",
            "not admission of any component the CLI calls: NP-ICP-NEUTRALIZER stays NOT_ADMITTED; Hall thrust stays NOT_EVALUATED"
        ],
    });
    for k in ["cases", "determinism", "static", "counts"] {
        report[k] = body[k].clone();
    }
    if let Some(dir) = opt(&args, "--report-dir") {
        let dir = repo.join(dir);
        let mut js = serde_json::to_string_pretty(&report).expect("report serializes");
        js.push('\n');
        if let Err(e) = std::fs::write(dir.join("acceptance_report_v2.json"), js)
            .and_then(|_| std::fs::write(dir.join("acceptance_report_v2.md"), md(&report)))
        {
            eprintln!("cannot write the report: {e}");
            return ExitCode::from(2);
        }
    } else {
        println!("{}", serde_json::to_string_pretty(&report).expect("report serializes"));
    }
    eprintln!("verdict: {}", report["verdict"]);
    for p in &problems {
        eprintln!("  {p}");
    }
    if accepted {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}
