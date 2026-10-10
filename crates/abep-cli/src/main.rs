//! `abep`: the deterministic ABEP simulator CLI (SC-WP-13). Grammar, outputs and exit codes: `abep_cli` and
//! docs/rust_migration/contracts/NI-ABEP-CLI/acceptance_v2.json.

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    let exit = abep_cli::run(&args, &cwd);
    if let Some(line) = &exit.stdout {
        println!("{line}");
    }
    if let Some(msg) = &exit.stderr {
        eprintln!("{msg}");
    }
    ExitCode::from(exit.code)
}
