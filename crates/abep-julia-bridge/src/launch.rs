//! The only place a Julia process is spawned. Fail closed at every step: the pin is verified (Rust side; Julia's
//! check_pin() runs again inside the driver), every input file is re-hashed against the job, `julia --version` must
//! report the Manifest's Julia version, a non-zero exit is MODEL_ERROR, and the sidecar records the run. Normal CI
//! never calls this (registered platform tests PT-01 / PT-02 do).

use crate::jobs::JobSpec;
use crate::pin::verify_pin;
use crate::sidecar::JuliaRunSidecar;
use abep_hall::py;
use abep_provenance::git::Git;
use abep_provenance::{read_verified, sha256_file};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::path::Path;

fn model(message: impl Into<String>) -> AbepError {
    AbepError::Model { message: message.into() }
}

/// Host name (`uname -n`), from the kernel; absent is INCOMPLETE_EVIDENCE, never a default.
pub fn host_name() -> AbepResult<String> {
    std::fs::read_to_string("/proc/sys/kernel/hostname")
        .map(|s| s.trim().to_string())
        .ok()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| AbepError::IncompleteEvidence { message: "host name not readable".into() })
}

/// `julia --version` of the job's program under the job's environment: "julia version X.Y.Z" -> "X.Y.Z".
pub fn julia_version(job: &JobSpec) -> AbepResult<String> {
    let mut c = std::process::Command::new(&job.program);
    c.arg("--version").current_dir(&job.cwd).env_clear().envs(&job.env);
    let out = c.output().map_err(|e| model(format!("cannot run {} --version: {e}", job.program)))?;
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    text.strip_prefix("julia version ")
        .map(str::to_string)
        .filter(|_| out.status.success())
        .ok_or_else(|| model(format!("unexpected `{} --version` output: {text:?}", job.program)))
}

/// Launch `job` from the repository `repo`; returns the sidecar written next to its first output.
pub fn launch(repo: &str, job: &JobSpec, contract_id: &str) -> AbepResult<JuliaRunSidecar> {
    let pin = verify_pin(repo)?;
    let mut inputs = BTreeMap::new();
    for (rel, sha) in &job.inputs {
        read_verified(&Path::new(repo).join(rel), sha)?;
        inputs.insert(rel.clone(), sha.clone());
    }
    let jv = julia_version(job)?;
    if jv != py::py_str(&pin.julia_version) {
        return Err(model(format!("julia {jv} is not the Manifest's {}", py::py_str(&pin.julia_version))));
    }
    let host = host_name()?;
    let rust_commit = Git::new(Path::new(repo))
        .stdout(&["rev-parse", "--verify", "HEAD^{commit}"])
        .map_err(|e| AbepError::IncompleteEvidence { message: e })?;
    for out in &job.outputs {
        if let Some(parent) = Path::new(out).parent() {
            std::fs::create_dir_all(parent).map_err(|e| model(format!("{}: {e}", parent.display())))?;
        }
    }
    let status = job.command().status().map_err(|e| model(format!("cannot start {}: {e}", job.program)))?;
    if !status.success() {
        return Err(model(format!("julia job {:?} exited with {status}", job.argv())));
    }
    let mut outputs = BTreeMap::new();
    for out in &job.outputs {
        outputs.insert(out.clone(), sha256_file(Path::new(out))?);
    }
    let sidecar = JuliaRunSidecar {
        julia_version: jv,
        hallthruster_commit: py::py_str(&pin.commit),
        threads_blas: job.threads.0.clone(),
        host,
        argv: job.argv(),
        input_sha256: inputs,
        output_sha256: outputs,
        rust_commit,
        contract_id: contract_id.to_string(),
    };
    if let Some(first) = job.outputs.first() {
        let p = JuliaRunSidecar::path_for(first);
        std::fs::write(&p, sidecar.to_json()).map_err(|e| model(format!("{p}: {e}")))?;
    }
    Ok(sidecar)
}
