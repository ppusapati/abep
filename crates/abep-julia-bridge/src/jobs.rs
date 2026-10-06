//! Job specifications of the HallThruster.jl process boundary (hall_physics_boundary.process_boundary): program,
//! argv, working directory (the repository root), an explicit environment (allow-list pass-through, pinned thread /
//! BLAS settings, job variables) and the input files with their expected sha256. `JobSpec::command` builds the
//! `std::process::Command`; only `launch::launch` spawns it.

use crate::manifests::{self, DRIVER, SHARDS};
use abep_hall::py::{self, PyValue};
use abep_hall::{HallError, HallResult};
use std::collections::BTreeMap;
use std::process::Command;

/// Variables passed through from the parent environment when present.
pub const PASS_THROUGH: [&str; 4] = ["HOME", "JULIA_DEPOT_PATH", "PATH", "TMPDIR"];
/// Thread / BLAS settings pinned per job and recorded in the sidecar.
pub const THREAD_VARS: [&str; 4] = ["JULIA_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"];
/// The one job variable a Rust job may set (construction smoke only).
pub const SMOKE_VAR: &str = "P5N2_SMOKE";

/// Pinned thread / BLAS settings of one job (absent = unset in the child).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ThreadSettings(pub BTreeMap<String, Option<String>>);

impl ThreadSettings {
    /// The parent's values (the Python-launched job inherits them).
    pub fn from_parent(lookup: &dyn Fn(&str) -> Option<String>) -> Self {
        ThreadSettings(THREAD_VARS.iter().map(|k| (k.to_string(), lookup(k))).collect())
    }

    /// Explicit values for every variable.
    pub fn pinned(values: [(&str, &str); 4]) -> Self {
        ThreadSettings(values.iter().map(|(k, v)| (k.to_string(), Some(v.to_string()))).collect())
    }
}

/// One Julia job.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JobSpec {
    pub program: String,
    pub args: Vec<String>,
    pub cwd: String,
    /// The complete child environment (`env_clear` first).
    pub env: BTreeMap<String, String>,
    pub threads: ThreadSettings,
    /// Repository-relative input files and the sha256 they must have at launch.
    pub inputs: Vec<(String, String)>,
    /// Output files the run writes (hashed into the sidecar).
    pub outputs: Vec<String>,
}

impl JobSpec {
    /// The child process, not spawned.
    pub fn command(&self) -> Command {
        let mut c = Command::new(&self.program);
        c.args(&self.args).current_dir(&self.cwd).env_clear().envs(&self.env);
        c
    }

    /// `program` followed by `args`.
    pub fn argv(&self) -> Vec<String> {
        std::iter::once(self.program.clone()).chain(self.args.iter().cloned()).collect()
    }
}

/// The child environment: pass-through allow-list, then the pinned thread settings, then the job variables.
pub fn child_env(
    lookup: &dyn Fn(&str) -> Option<String>,
    threads: &ThreadSettings,
    job_vars: &[(&str, &str)],
) -> BTreeMap<String, String> {
    let mut env: BTreeMap<String, String> = BTreeMap::new();
    for k in PASS_THROUGH {
        if let Some(v) = lookup(k) {
            env.insert(k.to_string(), v);
        }
    }
    for (k, v) in &threads.0 {
        if let Some(v) = v {
            env.insert(k.clone(), v.clone());
        }
    }
    for (k, v) in job_vars {
        env.insert(k.to_string(), v.to_string());
    }
    env
}

fn manifest_inputs(m: &PyValue) -> HallResult<Vec<(String, String)>> {
    let mut inputs = vec![
        (DRIVER.to_string(), py::py_str(py::getitem(m, "driver_sha256")?)),
        (manifests::LOCK_REL.to_string(), py::py_str(py::getitem(m, "prereg_lock_sha256")?)),
    ];
    let PyValue::Dict(chem) = py::getitem(m, "chemistry")? else {
        return Err(HallError::type_error("manifest chemistry is not a mapping"));
    };
    for (c, sha) in chem {
        inputs.push((format!("hallthruster_bridge/propellants/{}", py::py_str(c)), py::py_str(sha)));
    }
    Ok(inputs)
}

/// Shard `shard` of a campaign manifest: `julia --project=hallthruster_bridge <driver> <out>/s<i>.jsonl <mode> <i> 4
/// <chemistry>` from the repository root.
pub fn campaign_shard_job(
    repo: &str,
    manifest: &PyValue,
    shard: usize,
    out_dir: &str,
    threads: &ThreadSettings,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> HallResult<JobSpec> {
    if shard >= SHARDS {
        return Err(HallError::value("SHARD", format!("shard {shard} outside 0..{SHARDS}")));
    }
    let mode = py::py_str(py::getitem(manifest, "mode")?);
    let chems: Vec<String> = py::iterate(py::getitem(manifest, "chemistry")?)?.iter().map(py::py_str).collect();
    let out = format!("{out_dir}/s{shard}.jsonl");
    let args = vec![
        "--project=hallthruster_bridge".to_string(),
        DRIVER.to_string(),
        out.clone(),
        mode,
        shard.to_string(),
        SHARDS.to_string(),
        chems.join(","),
    ];
    Ok(JobSpec {
        program: "julia".into(),
        args,
        cwd: repo.to_string(),
        env: child_env(lookup, threads, &[]),
        threads: threads.clone(),
        inputs: manifest_inputs(manifest)?,
        outputs: vec![out],
    })
}

/// The julia-smoke.yml construction smoke: one job (shard 0 of NJOBS = screening candidates x cases) of n2_n.toml in
/// vacuum mode with P5N2_SMOKE=1 (2 us, targets stripped, never score-bearing).
pub fn smoke_job(
    repo: &str,
    out_path: &str,
    threads: &ThreadSettings,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> HallResult<JobSpec> {
    let (crit, cands, cases) = manifests::inputs(repo)?;
    let njobs = cands.len() * cases.len();
    let pins = py::getitem(py::getitem(&crit, "inputs_pinned")?, "chemistry_configs_sha256")?;
    let driver_sha = abep_provenance::sha256_hex(&py::read_file(&py::join(repo, DRIVER))?);
    let lock_sha = abep_provenance::sha256_hex(&py::read_file(&py::join(repo, manifests::LOCK_REL))?);
    Ok(JobSpec {
        program: "julia".into(),
        args: vec![
            "--project=hallthruster_bridge".into(),
            DRIVER.into(),
            out_path.into(),
            "vacuum".into(),
            "0".into(),
            njobs.to_string(),
            "n2_n.toml".into(),
        ],
        cwd: repo.to_string(),
        env: child_env(lookup, threads, &[(SMOKE_VAR, "1")]),
        threads: threads.clone(),
        inputs: vec![
            (DRIVER.into(), driver_sha),
            (manifests::LOCK_REL.into(), lock_sha),
            ("hallthruster_bridge/propellants/n2_n.toml".into(), py::py_str(py::getitem(pins, "n2_n.toml")?)),
        ],
        outputs: vec![out_path.into()],
    })
}

/// Keys of shard `shard` under the driver rule: jobs = candidates x chemistry x cases (driver order), job ij (1-based)
/// belongs to shard (ij - 1) % nshards.
pub fn shard_keys(repo: &str, manifest: &PyValue, shard: usize, nshards: usize) -> HallResult<Vec<String>> {
    let (_, cands, cases) = manifests::inputs(repo)?;
    let mode = py::py_str(py::getitem(manifest, "mode")?);
    let chems: Vec<String> = py::iterate(py::getitem(manifest, "chemistry")?)?.iter().map(py::py_str).collect();
    let mut out = Vec::new();
    let mut ij = 0usize;
    for cd in &cands {
        for ch in &chems {
            for cs in &cases {
                if ij % nshards == shard {
                    out.push(format!("{cd}|{ch}|{cs}|{mode}"));
                }
                ij += 1;
            }
        }
    }
    out.sort();
    Ok(out)
}

/// Keys already present in shard outputs (the driver resumes by skipping them).
pub fn done_keys(paths: &[String]) -> HallResult<Vec<String>> {
    let mut out = Vec::new();
    for p in paths {
        if !py::isfile(p) {
            continue;
        }
        for line in py::read_text(p)?.split_inclusive('\n') {
            if !py::py_strip(line).is_empty() {
                out.push(py::py_str(py::getitem(&py::load_json_bytes(line.as_bytes())?, "key")?));
            }
        }
    }
    Ok(out)
}
