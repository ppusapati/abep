//! Case runner of the registered abep_core build-equivalence check
//! (`docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/addendum_v1.json`).
//!
//! Runs the Kernel-1 functions of `abep_core` on every case of `cases_v1.json` and returns one sha256 per case over
//! the registered byte serialization (f64 and i64 little-endian, bool one byte). The same digests from the recorded
//! extension (B0) are the reference; any build of this crate must reproduce them bit for bit.

use abep_core::rng::Rng;
use abep_core::tpmc::{self, Scattering, TraceParams, V3};
use abep_provenance::{read_bytes, sha256_hex};
use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::Path;

/// Registered case file, relative to the repository root.
pub const CASES_PATH: &str = "docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/cases_v1.json";
/// sha256 of the case file registered in addendum_v1.json.
pub const CASES_SHA256: &str = "8baf28d54b37aa9c6d4bab3b209c0f34b7f26afc5ea41dafd56f5bd39965d564";

#[derive(Debug, Deserialize)]
pub struct CaseFile {
    pub schema: String,
    pub normal_sets: BTreeMap<String, Vec<[f64; 3]>>,
    pub cases: Vec<Case>,
}

#[derive(Debug, Deserialize)]
pub struct Case {
    pub id: String,
    pub kernel: String,
    pub n: usize,
    pub seed: u64,
    pub input_seed: Option<u64>,
    pub f64: BTreeMap<String, Option<f64>>,
    pub normal_set: Option<String>,
    pub scattering: Option<String>,
    pub max_hits: Option<usize>,
    pub max_hits_cap: Option<usize>,
}

/// One case's result: id and lower-case hex sha256 of its serialized outputs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CaseDigest {
    pub id: String,
    pub sha256: String,
}

fn model(msg: String) -> AbepError {
    AbepError::Model { message: msg }
}

impl Case {
    fn get(&self, key: &str) -> AbepResult<f64> {
        self.f64
            .get(key)
            .copied()
            .flatten()
            .ok_or_else(|| model(format!("build-equivalence case {}: missing f64 input {key}", self.id)))
    }

    fn opt(&self, key: &str) -> Option<f64> {
        self.f64.get(key).copied().flatten()
    }
}

fn put_v3(buf: &mut Vec<u8>, v: &[V3]) {
    for r in v {
        for x in r {
            buf.extend_from_slice(&x.to_le_bytes());
        }
    }
}

fn put_bool(buf: &mut Vec<u8>, v: &[bool]) {
    buf.extend(v.iter().map(|&b| u8::from(b)));
}

fn normals(file: &CaseFile, case: &Case) -> AbepResult<Vec<V3>> {
    let name = case.normal_set.as_deref().ok_or_else(|| model(format!("case {}: no normal_set", case.id)))?;
    let set =
        file.normal_sets.get(name).ok_or_else(|| model(format!("case {}: unknown normal set {name}", case.id)))?;
    if set.is_empty() {
        return Err(model(format!("normal set {name} is empty")));
    }
    Ok((0..case.n).map(|i| set[i % set.len()]).collect())
}

fn tpmc_err(case: &Case, e: tpmc::TpmcError) -> AbepError {
    model(format!("build-equivalence case {}: abep_core refused: {e}", case.id))
}

/// Serialized outputs of one case (the bytes that are hashed).
pub fn case_bytes(file: &CaseFile, case: &Case) -> AbepResult<Vec<u8>> {
    let mut buf = Vec::new();
    let entry = |seed: u64| -> AbepResult<Vec<V3>> {
        let mut rng = Rng::new(seed);
        tpmc::flux_weighted_entry(
            &mut rng,
            case.n,
            case.get("v_drift")?,
            case.get("theta")?,
            case.get("t")?,
            case.get("m")?,
        )
        .map_err(|e| tpmc_err(case, e))
    };
    let input_seed = || case.input_seed.ok_or_else(|| model(format!("case {}: no input_seed", case.id)));
    match case.kernel.as_str() {
        "K1_entry" => put_v3(&mut buf, &entry(case.seed)?),
        "K2_diffuse" => {
            let nr = normals(file, case)?;
            let mut rng = Rng::new(case.seed);
            put_v3(&mut buf, &tpmc::diffuse(&mut rng, &nr, case.get("t_w")?, case.get("m")?));
        }
        "K3_cll" => {
            let v_in = entry(input_seed()?)?;
            let nr = normals(file, case)?;
            let mut rng = Rng::new(case.seed);
            let out = tpmc::cll(
                &mut rng,
                &v_in,
                &nr,
                case.get("t_w")?,
                case.get("m")?,
                case.get("alpha_n")?,
                case.get("alpha_t")?,
            )
            .map_err(|e| tpmc_err(case, e))?;
            put_v3(&mut buf, &v_in);
            put_v3(&mut buf, &out);
        }
        "K4_trace" => {
            let v0 = entry(input_seed()?)?;
            let scattering =
                Scattering::parse(case.scattering.as_deref().unwrap_or("")).map_err(|e| tpmc_err(case, e))?;
            let p = TraceParams {
                r: case.get("r")?,
                l: case.get("l")?,
                alpha: case.get("alpha")?,
                t_w: case.get("t_w")?,
                m: case.get("m")?,
                max_hits: case.max_hits.ok_or_else(|| model(format!("case {}: no max_hits", case.id)))?,
                scattering,
                alpha_n: case.opt("alpha_n"),
                alpha_t: case.opt("alpha_t"),
                unresolved_tol: case.get("unresolved_tol")?,
                max_hits_cap: case.max_hits_cap.ok_or_else(|| model(format!("case {}: no max_hits_cap", case.id)))?,
            };
            let mut rng = Rng::new(case.seed);
            let res = tpmc::trace_channel(&mut rng, &v0, &p).map_err(|e| tpmc_err(case, e))?;
            put_v3(&mut buf, &v0);
            put_bool(&mut buf, &res.collected);
            put_v3(&mut buf, &res.v);
            for h in &res.hits {
                buf.extend_from_slice(&h.to_le_bytes());
            }
            put_bool(&mut buf, &res.back);
            buf.extend_from_slice(&res.unresolved.to_le_bytes());
        }
        "K5_clausing" => {
            let mut rng = Rng::new(case.seed);
            let k = tpmc::clausing_transmission(
                &mut rng,
                case.get("r")?,
                case.get("l")?,
                case.get("alpha")?,
                case.get("t_w")?,
                case.get("m")?,
                case.n,
            )
            .map_err(|e| tpmc_err(case, e))?;
            buf.extend_from_slice(&k.to_le_bytes());
        }
        other => return Err(model(format!("case {}: unknown kernel {other}", case.id))),
    }
    Ok(buf)
}

/// Load the registered case file under `repo_root`, verifying its registered sha256.
pub fn load_cases(repo_root: &Path) -> AbepResult<CaseFile> {
    let path = repo_root.join(CASES_PATH);
    let bytes = abep_provenance::read_verified(&path, CASES_SHA256)?;
    let file: CaseFile = serde_json::from_slice(&bytes)
        .map_err(|e| AbepError::Schema { path: path.display().to_string(), message: e.to_string() })?;
    if file.schema != "abep_core_build_equivalence_cases_v1" {
        return Err(AbepError::Schema { path: path.display().to_string(), message: format!("schema {}", file.schema) });
    }
    Ok(file)
}

/// Run every case; one digest per case in file order.
pub fn run_all(file: &CaseFile) -> AbepResult<Vec<CaseDigest>> {
    file.cases.iter().map(|c| Ok(CaseDigest { id: c.id.clone(), sha256: sha256_hex(&case_bytes(file, c)?) })).collect()
}

/// Total digest: sha256 of the per-case hex digests joined by '\n' in case order.
pub fn total_digest(digests: &[CaseDigest]) -> String {
    let joined = digests.iter().map(|d| d.sha256.as_str()).collect::<Vec<_>>().join("\n");
    sha256_hex(joined.as_bytes())
}

/// Read a JSON file without hash pinning (results written by the check itself).
pub fn read_json(path: &Path) -> AbepResult<serde_json::Value> {
    let bytes = read_bytes(path)?;
    serde_json::from_slice(&bytes)
        .map_err(|e| AbepError::Schema { path: path.display().to_string(), message: e.to_string() })
}
