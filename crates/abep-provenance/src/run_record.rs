//! Run-record sidecar: the provenance every Rust-produced result carries (programme_v3_1 RM-R03 / RM-R10; CLAUDE.md
//! "future campaigns record thread/BLAS environment, Julia version and HallThruster commit per run").
//!
//! Every hash is verified while it is captured: the model set and the architecture against `config/MANIFEST.json`, the
//! design-state set against its reference record. A missing or mismatching input is an error, never an empty field.
//! The JSON form is deterministic (fixed field order, sorted maps, two-space indent, trailing newline).

use crate::git::Git;
use crate::{read_bytes, read_verified, sha256_hex, ConfigManifest};
use abep_types::{AbepError, AbepResult};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;

pub const RUN_RECORD_SCHEMA: &str = "abep_run_record_v1";
/// `rustc --version` of the compiler that built this crate (build.rs).
pub const RUSTC_VERSION: &str = env!("ABEP_RUSTC_VERSION");
pub const MODEL_SET: &str = "model_set/physics_model_set_v1.json";
pub const ARCHITECTURE: &str = "architecture/hall_icp_neutralizer_v1.json";
pub const DESIGN_STATE_SET_REF: &str = "environment/design_state_set_ref_v1.json";
pub const HALLTHRUSTER_PINNED: &str = "hallthruster_bridge/PINNED.toml";
/// Thread / BLAS / Julia settings recorded with every run (absent variables are recorded as null).
pub const THREAD_ENV_VARS: [&str; 8] = [
    "BLIS_NUM_THREADS",
    "JULIA_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "RAYON_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HashedFile {
    pub path: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DesignStateSet {
    /// The reference record in config/ (pinned by config/MANIFEST.json).
    pub reference: HashedFile,
    /// The frozen design-state file it references, verified against the referenced sha256.
    pub path: String,
    pub sha256: String,
    pub n_states: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HallThrusterPin {
    pub pinned_toml: HashedFile,
    pub version: String,
    pub commit: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Threads {
    pub available_parallelism: Option<u64>,
    pub env: BTreeMap<String, Option<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RunRecord {
    pub schema: String,
    pub implementation: String,
    pub git_commit: String,
    pub git_dirty: bool,
    pub rustc: String,
    pub cargo_lock_sha256: String,
    pub config_manifest: HashedFile,
    pub model_set: HashedFile,
    pub architecture: HashedFile,
    pub design_state_set: DesignStateSet,
    pub hallthruster: HallThrusterPin,
    pub threads: Threads,
    pub contract_id: Option<String>,
}

fn incomplete(message: impl Into<String>) -> AbepError {
    AbepError::IncompleteEvidence { message: message.into() }
}

fn schema_err(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: message.into() }
}

/// `[hallthruster]` `version` and `commit` of PINNED.toml. Strict subset reader: inside that table every line must be
/// blank, a comment, or `key = "single-line string"` (optionally followed by a comment); anything else is refused.
pub fn parse_hallthruster_pin(text: &str) -> AbepResult<(String, String)> {
    let mut in_table = false;
    let mut found: BTreeMap<String, String> = BTreeMap::new();
    for line in text.lines() {
        let t = line.trim();
        if t.starts_with('[') {
            in_table = t == "[hallthruster]";
            continue;
        }
        if !in_table || t.is_empty() || t.starts_with('#') {
            continue;
        }
        let (key, rest) = t.split_once('=').ok_or_else(|| schema_err(HALLTHRUSTER_PINNED, format!("line {t:?}")))?;
        let rest = rest.trim();
        let body = rest
            .strip_prefix('"')
            .and_then(|r| r.split_once('"'))
            .filter(|(v, tail)| !v.contains('\\') && (tail.trim().is_empty() || tail.trim().starts_with('#')))
            .map(|(v, _)| v.to_string())
            .ok_or_else(|| schema_err(HALLTHRUSTER_PINNED, format!("unsupported value in line {t:?}")))?;
        if found.insert(key.trim().to_string(), body).is_some() {
            return Err(schema_err(HALLTHRUSTER_PINNED, format!("duplicate key {}", key.trim())));
        }
    }
    let version =
        found.remove("version").ok_or_else(|| schema_err(HALLTHRUSTER_PINNED, "no [hallthruster] version"))?;
    let commit = found.remove("commit").ok_or_else(|| schema_err(HALLTHRUSTER_PINNED, "no [hallthruster] commit"))?;
    if commit.len() != 40 || !commit.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
        return Err(schema_err(HALLTHRUSTER_PINNED, format!("commit {commit:?} is not 40 lower-case hex digits")));
    }
    Ok((version, commit))
}

fn hashed(path: &str, bytes: &[u8]) -> HashedFile {
    HashedFile { path: path.to_string(), sha256: sha256_hex(bytes) }
}

impl RunRecord {
    /// Capture the record for the repository at `repo_root`, reading thread settings from the process environment.
    pub fn capture(repo_root: &Path, contract_id: Option<&str>) -> AbepResult<Self> {
        Self::capture_with_env(repo_root, contract_id, &|k| std::env::var(k).ok())
    }

    /// As `capture`, with an injected environment lookup.
    pub fn capture_with_env(
        repo_root: &Path,
        contract_id: Option<&str>,
        env: &dyn Fn(&str) -> Option<String>,
    ) -> AbepResult<Self> {
        if RUSTC_VERSION.is_empty() {
            return Err(incomplete("rustc version was not recorded at build time"));
        }
        let git = Git::new(repo_root);
        let commit = git.stdout(&["rev-parse", "--verify", "HEAD^{commit}"]).map_err(incomplete)?;
        if commit.len() != 40 {
            return Err(incomplete(format!("git commit {commit:?} is not a full object id")));
        }
        let dirty = !git.stdout(&["status", "--porcelain", "--untracked-files=no"]).map_err(incomplete)?.is_empty();

        let manifest_bytes = read_bytes(&repo_root.join("config").join("MANIFEST.json"))?;
        let manifest = ConfigManifest::load(repo_root)?;
        let model_set = manifest.read_verified(repo_root, MODEL_SET)?;
        let architecture = manifest.read_verified(repo_root, ARCHITECTURE)?;
        let ds_ref_bytes = manifest.read_verified(repo_root, DESIGN_STATE_SET_REF)?;
        let ds_ref_path = format!("config/{DESIGN_STATE_SET_REF}");
        let ds_ref: Value =
            serde_json::from_slice(&ds_ref_bytes).map_err(|e| schema_err(&ds_ref_path, e.to_string()))?;
        let field = |k: &str| ds_ref.get(k).ok_or_else(|| schema_err(&ds_ref_path, format!("missing {k}")));
        let ds_path = field("path")?.as_str().ok_or_else(|| schema_err(&ds_ref_path, "path is not a string"))?;
        let ds_sha = field("sha256")?.as_str().ok_or_else(|| schema_err(&ds_ref_path, "sha256 is not a string"))?;
        let n_states =
            field("n_states")?.as_u64().ok_or_else(|| schema_err(&ds_ref_path, "n_states is not an integer"))?;
        read_verified(&repo_root.join(ds_path), ds_sha)?;

        let pinned = read_bytes(&repo_root.join(HALLTHRUSTER_PINNED))?;
        let pinned_text = std::str::from_utf8(&pinned).map_err(|e| schema_err(HALLTHRUSTER_PINNED, e.to_string()))?;
        let (version, ht_commit) = parse_hallthruster_pin(pinned_text)?;
        let cargo_lock = read_bytes(&repo_root.join("Cargo.lock"))?;

        Ok(RunRecord {
            schema: RUN_RECORD_SCHEMA.into(),
            implementation: "rust".into(),
            git_commit: commit,
            git_dirty: dirty,
            rustc: RUSTC_VERSION.into(),
            cargo_lock_sha256: sha256_hex(&cargo_lock),
            config_manifest: hashed("config/MANIFEST.json", &manifest_bytes),
            model_set: hashed(&format!("config/{MODEL_SET}"), &model_set),
            architecture: hashed(&format!("config/{ARCHITECTURE}"), &architecture),
            design_state_set: DesignStateSet {
                reference: hashed(&ds_ref_path, &ds_ref_bytes),
                path: ds_path.into(),
                sha256: ds_sha.into(),
                n_states,
            },
            hallthruster: HallThrusterPin {
                pinned_toml: hashed(HALLTHRUSTER_PINNED, &pinned),
                version,
                commit: ht_commit,
            },
            threads: Threads {
                available_parallelism: std::thread::available_parallelism().ok().map(|n| n.get() as u64),
                env: THREAD_ENV_VARS.iter().map(|k| (k.to_string(), env(k))).collect(),
            },
            contract_id: contract_id.map(str::to_string),
        })
    }

    /// Deterministic JSON: the same record always gives the same bytes.
    pub fn to_json(&self) -> String {
        let mut s = serde_json::to_string_pretty(self).expect("a run record always serializes");
        s.push('\n');
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PINNED: &str = "# header\n[hallthruster]\npackage = \"HallThruster.jl\"\nversion = \"0.23.1\"\n\
        commit = \"bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5\"   # comment\n\n[julia]\nminimum = \"1.10\"\nlist = [\n  \"x\",\n]\n";

    #[test]
    fn hallthruster_pin_reader_is_strict() {
        let (v, c) = parse_hallthruster_pin(PINNED).unwrap();
        assert_eq!((v.as_str(), c.as_str()), ("0.23.1", "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5"));
        for bad in [
            PINNED.replace("version = \"0.23.1\"", "version = 0.23"),
            PINNED.replace("commit = \"bfb3019", "commit = \"BFB3019"),
            PINNED.replace("[hallthruster]\n", "[hallthruster]\nversion = \"9\"\n"),
            PINNED.replace("[hallthruster]", "[other]"),
            PINNED.replace("package = \"HallThruster.jl\"", "package = \"a\\\"b\""),
            PINNED.replace("package = \"HallThruster.jl\"", "multi = [\"a\","),
        ] {
            assert!(parse_hallthruster_pin(&bad).is_err(), "{bad}");
        }
    }

    fn sample() -> RunRecord {
        let h = |p: &str| HashedFile { path: p.into(), sha256: "0".repeat(64) };
        RunRecord {
            schema: RUN_RECORD_SCHEMA.into(),
            implementation: "rust".into(),
            git_commit: "a".repeat(40),
            git_dirty: false,
            rustc: "rustc 1.94.1 (e408947bf 2026-03-25)".into(),
            cargo_lock_sha256: "1".repeat(64),
            config_manifest: h("config/MANIFEST.json"),
            model_set: h("config/model_set/physics_model_set_v1.json"),
            architecture: h("config/architecture/hall_icp_neutralizer_v1.json"),
            design_state_set: DesignStateSet {
                reference: h("config/environment/design_state_set_ref_v1.json"),
                path: "abep_sim/data/x.json".into(),
                sha256: "2".repeat(64),
                n_states: 196,
            },
            hallthruster: HallThrusterPin {
                pinned_toml: h(HALLTHRUSTER_PINNED),
                version: "0.23.1".into(),
                commit: "b".repeat(40),
            },
            threads: Threads {
                available_parallelism: Some(4),
                env: [("OMP_NUM_THREADS", Some("1")), ("JULIA_NUM_THREADS", None)]
                    .into_iter()
                    .map(|(k, v)| (k.to_string(), v.map(str::to_string)))
                    .collect(),
            },
            contract_id: Some("PARITY-X-V1".into()),
        }
    }

    #[test]
    fn json_is_deterministic_ordered_and_round_trips() {
        let r = sample();
        let a = r.to_json();
        assert_eq!(a, sample().to_json());
        assert!(a.ends_with("}\n") && a.starts_with("{\n  \"schema\": \"abep_run_record_v1\",\n  \"implementation\""));
        let keys: Vec<usize> = ["\"schema\"", "\"git_commit\"", "\"rustc\"", "\"design_state_set\"", "\"contract_id\""]
            .iter()
            .map(|k| a.find(k).unwrap())
            .collect();
        assert!(keys.windows(2).all(|w| w[0] < w[1]), "field order is fixed");
        assert!(a.find("JULIA_NUM_THREADS").unwrap() < a.find("OMP_NUM_THREADS").unwrap(), "env keys sorted");
        assert!(a.contains("\"JULIA_NUM_THREADS\": null"));
        assert_eq!(serde_json::from_str::<RunRecord>(&a).unwrap(), r);
    }
}
