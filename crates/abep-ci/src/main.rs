//! `abep-ci <check> [--root PATH]`: exit 0 pass, 1 fail or not evaluated, 2 usage.
//!
//!   bid-source-guard                         A9.29 sec. 3 guard on the repository (needs full git history)
//!   test-register                            Rust-era test rule: no #[ignore] outside the platform-test register
//!   groundtest-isolation                     no workspace crate depends on abep-groundtest (cargo metadata)
//!   run-record [--contract-id ID]            print the run-record sidecar of the repository
//!   bid-guard-acceptance --python-results F  the single acceptance run: writes acceptance_report_v1.json + .md

use abep_ci::{acceptance_report, groundtest, test_register};
use abep_provenance::bid_guard::{evaluate, GuardInputs, GuardStatus};
use abep_provenance::find_repo_root;
use abep_provenance::run_record::RunRecord;
use std::path::PathBuf;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn run(args: &[String]) -> Result<bool, String> {
    let root = match opt(args, "--root") {
        Some(r) => PathBuf::from(r),
        None => {
            let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
            find_repo_root(&cwd).map_err(|e| e.to_string())?
        }
    };
    match args.first().map(String::as_str) {
        Some("bid-source-guard") => {
            let r = evaluate(&GuardInputs::repository(&root));
            print!("{}", r.render());
            Ok(r.overall == GuardStatus::Pass)
        }
        Some("test-register") => {
            let r = test_register::check(&root)?;
            println!(
                "test register: {} file(s) scanned, {} ignore attribute(s), {} registered platform test(s), {} violation(s)",
                r.files_scanned,
                r.ignore_attrs,
                r.registered,
                r.violations.len()
            );
            r.violations.iter().for_each(|v| println!("  {v}"));
            Ok(r.violations.is_empty())
        }
        Some("groundtest-isolation") => {
            let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".into());
            let r = groundtest::check_metadata(&groundtest::cargo_metadata(&cargo, &root)?)?;
            println!("{}", r.summary());
            r.violations.iter().for_each(|v| println!("  {v}"));
            Ok(r.violations.is_empty())
        }
        Some("run-record") => {
            let r = RunRecord::capture(&root, opt(args, "--contract-id").as_deref()).map_err(|e| e.to_string())?;
            print!("{}", r.to_json());
            Ok(true)
        }
        Some("bid-guard-acceptance") => {
            let f = opt(args, "--python-results").ok_or("--python-results FILE is required")?;
            let py = std::fs::read(&f).map_err(|e| format!("{f}: {e}"))?;
            let (v, md) = acceptance_report::build(&root, &py).map_err(|e| e.to_string())?;
            let json = serde_json::to_string_pretty(&v).map_err(|e| e.to_string())? + "\n";
            std::fs::write(root.join(acceptance_report::REPORT_JSON), json).map_err(|e| e.to_string())?;
            std::fs::write(root.join(acceptance_report::REPORT_MD), md).map_err(|e| e.to_string())?;
            println!("verdict {}", v["verdict"].as_str().unwrap_or("?"));
            Ok(v["verdict"] == "ACCEPTED")
        }
        _ => Err("usage: abep-ci bid-source-guard | test-register | groundtest-isolation | run-record | \
                  bid-guard-acceptance --python-results FILE  [--root PATH]"
            .into()),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("abep-ci: {e}");
            ExitCode::from(2)
        }
    }
}
