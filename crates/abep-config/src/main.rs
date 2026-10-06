//! `abep-config`: configuration build / check / verify (SC-WP-12; contract C-ABEP_SIM_CONFIGURATION_PY v1).
//!
//!   abep-config build [--check] [--repo DIR]   regenerate config/** (or compare byte for byte; exit 1 if stale)
//!   abep-config verify [--repo DIR]            verify every file pinned in config/MANIFEST.json (sha256 + bytes)
//!   abep-config eval CALLS.json                parity-harness interface (results as JSON on stdout)

use abep_config::builder::Builder;
use abep_provenance::{find_repo_root, ConfigManifest};
use std::path::PathBuf;
use std::process::ExitCode;

const USAGE: &str = "usage: abep-config build [--check] [--repo DIR] | verify [--repo DIR] | eval CALLS.json";

fn repo_arg(args: &[String]) -> Result<PathBuf, String> {
    if let Some(i) = args.iter().position(|a| a == "--repo") {
        return args.get(i + 1).map(PathBuf::from).ok_or_else(|| USAGE.to_string());
    }
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    find_repo_root(&cwd).map_err(|e| e.to_string())
}

fn run(args: &[String]) -> Result<u8, String> {
    match args.first().map(String::as_str) {
        Some("build") => {
            let b = Builder::new(&repo_arg(args)?);
            if args.iter().any(|a| a == "--check") {
                let c = b.check().map_err(|e| e.to_string())?;
                println!("{}", c.line);
                Ok(c.exit as u8)
            } else {
                let n = b.write().map_err(|e| e.to_string())?;
                println!("wrote {n} files under config/");
                Ok(0)
            }
        }
        Some("verify") => {
            let root = repo_arg(args)?;
            let m = ConfigManifest::load(&root).map_err(|e| e.to_string())?;
            let n = m.verify_all(&root).map_err(|e| e.to_string())?;
            println!("OK: {n} config files verified against config/MANIFEST.json");
            Ok(0)
        }
        Some("eval") => {
            let path = args.get(1).ok_or_else(|| USAGE.to_string())?;
            let bytes = std::fs::read(path).map_err(|e| format!("{path}: {e}"))?;
            let text = abep_types::pyjson::read_text_utf8(&bytes).map_err(|e| e.to_string())?;
            let calls = abep_types::pyjson::loads(&text).map_err(|e| e.to_string())?;
            let out = abep_config::eval::eval_calls(&calls);
            let s = abep_types::pyjson::dumps(&out, &abep_types::pyjson::DumpOptions::default())
                .map_err(|e| e.to_string())?;
            println!("{s}");
            Ok(0)
        }
        _ => Err(USAGE.to_string()),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(code) => ExitCode::from(code),
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(1)
        }
    }
}
