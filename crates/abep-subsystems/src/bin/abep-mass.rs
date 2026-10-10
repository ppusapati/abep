//! `abep-mass`: the SC-WP-07 mass lane CLI.
//!
//! * `abep-mass eval <calls.json>`: evaluate a parity call list twice (determinism) and print the results.
//! * `abep-mass build-v5 <repo> <out_dir>`: write mass_power_a9_v5.json / MASS_POWER_A9_V5.md built from the pinned
//!   inputs (never into the frozen record directory).
//! * `abep-mass check-v5 <repo>`: exit 1 unless the committed record reproduces byte for byte.
//! * `abep-mass value-status <repo>` / `abep-mass gates <repo>`: the AL-07 value status (VS-01) and the fail-closed
//!   mass gates on the pinned record.

use abep_subsystems::mass::{eval, v5};
use abep_types::pyjson::{self, DumpOptions, PyException, Value};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

fn fail(e: PyException) -> ExitCode {
    eprintln!("{}: {}", e.class, e.message);
    ExitCode::from(2)
}

fn print_json(v: &Value) -> Result<(), PyException> {
    println!("{}", pyjson::dumps(v, &DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() })?);
    Ok(())
}

fn run(args: &[String]) -> Result<ExitCode, PyException> {
    match args {
        [cmd, calls] if cmd == "eval" => {
            let text = std::fs::read_to_string(calls)
                .map_err(|e| PyException::new("FileNotFoundError", format!("{calls}: {e}")))?;
            let (results, deterministic) = eval::eval_calls_twice(&pyjson::loads(&text)?)?;
            if !deterministic {
                eprintln!("MODEL_ERROR: the call list gave different results on a second evaluation");
                return Ok(ExitCode::from(3));
            }
            println!("{}", pyjson::dumps(&results, &DumpOptions::default())?);
            Ok(ExitCode::SUCCESS)
        }
        [cmd, repo, out] if cmd == "build-v5" => {
            let out = PathBuf::from(out);
            let record_dir = Path::new(repo).join(v5::LANE_REL);
            if out.canonicalize().ok() == record_dir.canonicalize().ok() {
                eprintln!("refused: the frozen record directory {} is never written", v5::LANE_REL);
                return Ok(ExitCode::from(2));
            }
            let (js, md) = v5::render(Path::new(repo))?;
            std::fs::create_dir_all(&out).map_err(|e| PyException::new("OSError", e.to_string()))?;
            for (name, text) in [(v5::JSON_NAME, js), (v5::MD_NAME, md)] {
                std::fs::write(out.join(name), text).map_err(|e| PyException::new("OSError", e.to_string()))?;
            }
            println!("wrote 2 files");
            Ok(ExitCode::SUCCESS)
        }
        [cmd, repo] if cmd == "check-v5" => {
            let stale = v5::check(Path::new(repo))?;
            if stale.is_empty() {
                println!("OK: 2 outputs reproduce");
                Ok(ExitCode::SUCCESS)
            } else {
                println!("STALE: {}", stale.join(", "));
                Ok(ExitCode::from(1))
            }
        }
        [cmd, repo] if cmd == "value-status" => {
            print_json(&v5::al07_value_status(Path::new(repo))?)?;
            Ok(ExitCode::SUCCESS)
        }
        [cmd, repo] if cmd == "gates" => {
            print_json(&v5::mass_gates(Path::new(repo), &v5::MissionXeLoad::NotAdmitted)?)?;
            Ok(ExitCode::SUCCESS)
        }
        _ => {
            eprintln!(
                "usage: abep-mass eval <calls.json> | build-v5 <repo> <out_dir> | check-v5 <repo> | value-status <repo> \
                 | gates <repo>"
            );
            Ok(ExitCode::from(64))
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    run(&args).unwrap_or_else(fail)
}
