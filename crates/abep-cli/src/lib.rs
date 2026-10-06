//! The deterministic `abep` CLI (SC-WP-13, NI-ABEP-CLI; acceptance record
//! `docs/rust_migration/contracts/NI-ABEP-CLI/acceptance_v2.json`).
//!
//! A thin orchestration over the admitted crates: it adds no physics, no requirement threshold and no PASS / FAIL.
//! Every command runs the registered pipeline (S-1 parse, S-2 output location, S-3 repository, S-4 config manifest,
//! S-5 run record, S-6 registered inputs, S-7 admission evidence, S-8 execution, S-9 outputs) and writes a result
//! record plus a run-record sidecar. Fail-closed statuses exit with distinct non-zero codes ([`output::exit_of`]).
//! The only subprocess is `git` (run record capture); nothing runs Python.

pub mod acceptance;
pub mod args;
pub mod commands;
pub mod output;
pub mod registry;

use abep_provenance::run_record::RunRecord;
use abep_types::EvalStatus;
use args::Invocation;
use output::{Header, Outcome, Reason};
use registry::ComponentState;
use std::path::{Path, PathBuf};

/// What the process prints and returns.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Exit {
    pub code: u8,
    pub stdout: Option<String>,
    pub stderr: Option<String>,
}

fn fail(code: u8, msg: impl Into<String>) -> Exit {
    Exit { code, stdout: None, stderr: Some(msg.into()) }
}

/// `p` with its nearest existing ancestor canonicalised and the remaining components appended.
fn canonical_prefix(p: &Path) -> PathBuf {
    let abs = if p.is_absolute() {
        p.to_path_buf()
    } else {
        std::env::current_dir().map(|d| d.join(p)).unwrap_or_else(|_| p.to_path_buf())
    };
    let mut rest = Vec::new();
    let mut cur = abs.as_path();
    loop {
        if let Ok(c) = cur.canonicalize() {
            let mut out = c;
            for r in rest.iter().rev() {
                out.push(r);
            }
            return out;
        }
        match (cur.file_name(), cur.parent()) {
            (Some(name), Some(parent)) => {
                rest.push(name.to_os_string());
                cur = parent;
            }
            _ => return abs,
        }
    }
}

fn is_repo_root(d: &Path) -> bool {
    d.join("Cargo.toml").is_file() && d.join("config").join("MANIFEST.json").is_file()
}

/// Write the result record and, with a run record, the sidecar.
fn finish(
    inv: &Invocation,
    run_record: Option<&RunRecord>,
    components: &[ComponentState],
    outcome: Outcome,
    threads_used: usize,
) -> Exit {
    let c = &inv.command;
    let stem = c.file_stem();
    let arguments = c.arguments();
    let header = Header { command: c.name(), arguments: &arguments, run_record, components };
    let text = output::result_text(&header, &outcome);
    let rpath = output::result_path(&inv.out, &stem);
    if let Err(e) = output::write_atomic(&rpath, &text) {
        return fail(output::EXIT_OUTPUT_WRITE, format!("OUTPUT_WRITE_ERROR: {e}"));
    }
    if let Some(rr) = run_record {
        let side = output::Sidecar {
            schema: output::SIDECAR_SCHEMA,
            command: c.name(),
            result_file: format!("{stem}.result.json"),
            result_sha256: output::sha256_text(&text),
            threads_requested: inv.threads,
            threads_used,
            run_record: rr,
        };
        if let Err(e) = output::write_atomic(&output::sidecar_path(&inv.out, &stem), &output::sidecar_text(&side)) {
            return fail(output::EXIT_OUTPUT_WRITE, format!("OUTPUT_WRITE_ERROR: {e}"));
        }
    }
    let line = format!("{} {} -> {stem}.result.json", outcome.status.as_str(), c.name());
    Exit {
        code: outcome.exit,
        stdout: Some(line),
        stderr: outcome.reason.map(|r| format!("{}: {}", r.code, r.message)),
    }
}

fn refuse_provenance(inv: &Invocation, code: &str, message: String) -> Exit {
    let o = Outcome {
        status: EvalStatus::ModelError,
        exit: output::EXIT_PROVENANCE,
        reason: Some(Reason::new(code, message)),
        payload: None,
    };
    finish(inv, None, &[], o, 0)
}

/// Run the CLI on `args` (without the program name) from working directory `cwd`.
pub fn run(args: &[String], cwd: &Path) -> Exit {
    // S-1
    let inv = match args::parse(args) {
        Ok(i) => i,
        Err(msg) => return fail(output::EXIT_USAGE, msg),
    };
    let root: Option<PathBuf> = match &inv.repo {
        Some(r) => is_repo_root(r).then(|| r.clone()),
        None => abep_provenance::find_repo_root(cwd).ok(),
    };
    // S-2: compared against the resolved root, or the given --repo directory when it is not a repository.
    let out_c = canonical_prefix(&inv.out);
    for base in root.iter().chain(inv.repo.iter()) {
        if out_c.starts_with(canonical_prefix(base)) {
            return fail(
                output::EXIT_OUTPUT_LOCATION,
                format!(
                    "REFUSED_OUTPUT_LOCATION: --out {} lies inside the repository {}",
                    inv.out.display(),
                    base.display()
                ),
            );
        }
    }
    if let Err(e) = std::fs::create_dir_all(&inv.out) {
        return fail(output::EXIT_OUTPUT_WRITE, format!("OUTPUT_WRITE_ERROR: {}: {e}", inv.out.display()));
    }
    // S-3
    let Some(root) = root else {
        let where_ = inv.repo.as_ref().map_or_else(|| cwd.display().to_string(), |r| r.display().to_string());
        return refuse_provenance(
            &inv,
            "REPOSITORY_NOT_FOUND",
            format!("{where_}: no repository root (Cargo.toml and config/MANIFEST.json)"),
        );
    };
    // S-4
    if let Err(e) = abep_provenance::ConfigManifest::load(&root).and_then(|m| m.verify_all(&root)) {
        return refuse_provenance(&inv, "CONFIG_MANIFEST_UNVERIFIED", e.to_string());
    }
    // S-5
    let rr = match RunRecord::capture(&root, Some(output::CONTRACT_ID)) {
        Ok(r) => r,
        Err(e) => return refuse_provenance(&inv, "RUN_RECORD_UNAVAILABLE", e.to_string()),
    };
    let components: Vec<ComponentState> =
        commands::components(&inv.command).iter().map(|c| registry::verify(&root, c)).collect();
    // S-6
    match commands::check_registered(&root, &inv.command) {
        Err(o) => return finish(&inv, Some(&rr), &components, o, 1),
        Ok(Err(msg)) => {
            let o = Outcome {
                status: EvalStatus::NotEvaluated,
                exit: output::EXIT_UNREGISTERED_INPUT,
                reason: Some(Reason::new("UNREGISTERED_INPUT", msg)),
                payload: None,
            };
            return finish(&inv, Some(&rr), &components, o, 1);
        }
        Ok(Ok(())) => {}
    }
    // S-7
    let unverified: Vec<String> = components.iter().filter_map(|c| c.problem.clone()).collect();
    if !unverified.is_empty() {
        let o = Outcome::status(
            EvalStatus::NotEvaluated,
            Some(Reason::new("COMPONENT_ADMISSION_UNVERIFIED", unverified.join("; "))),
            None,
        );
        return finish(&inv, Some(&rr), &components, o, 1);
    }
    // S-8
    let threads = inv.threads.unwrap_or_else(|| std::thread::available_parallelism().map_or(1, |n| n.get()));
    let ex = commands::execute(&commands::Ctx { root: &root, threads }, &inv.command);
    // S-9
    finish(&inv, Some(&rr), &components, ex.outcome, ex.threads_used)
}
