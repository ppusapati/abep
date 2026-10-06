//! Per-run execution-provenance sidecar: exactly the nine fields of simulation_completion_programme_v1_1.json
//! hall_physics_boundary.provenance_sidecar_per_run, in that order. Written next to the run's first output as
//! `<output>.sidecar.json`.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// (field name, programme label), in programme order.
pub const SIDECAR_FIELDS: [(&str, &str); 9] = [
    ("julia_version", "Julia version"),
    ("hallthruster_commit", "HallThruster commit"),
    ("threads_blas", "threads / BLAS"),
    ("host", "host"),
    ("argv", "argv"),
    ("input_sha256", "input sha256"),
    ("output_sha256", "output sha256"),
    ("rust_commit", "rust_commit"),
    ("contract_id", "contract_id"),
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct JuliaRunSidecar {
    pub julia_version: String,
    pub hallthruster_commit: String,
    /// The pinned thread / BLAS settings of the job (null = unset).
    pub threads_blas: BTreeMap<String, Option<String>>,
    pub host: String,
    pub argv: Vec<String>,
    /// Repository-relative input path -> sha256 verified before the launch.
    pub input_sha256: BTreeMap<String, String>,
    /// Output path -> sha256 after the run.
    pub output_sha256: BTreeMap<String, String>,
    pub rust_commit: String,
    pub contract_id: String,
}

impl JuliaRunSidecar {
    /// Deterministic JSON (fixed field order, sorted maps, two-space indent, trailing newline).
    pub fn to_json(&self) -> String {
        let mut s = serde_json::to_string_pretty(self).expect("a sidecar always serializes");
        s.push('\n');
        s
    }

    pub fn path_for(output: &str) -> String {
        format!("{output}.sidecar.json")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_has_exactly_the_nine_fields_in_order() {
        let s = JuliaRunSidecar {
            julia_version: "1.11.7".into(),
            hallthruster_commit: "b".repeat(40),
            threads_blas: [("JULIA_NUM_THREADS".to_string(), None)].into_iter().collect(),
            host: "h".into(),
            argv: vec!["julia".into()],
            input_sha256: BTreeMap::new(),
            output_sha256: BTreeMap::new(),
            rust_commit: "a".repeat(40),
            contract_id: "PARITY-C-JULIA-BRIDGE-LAUNCH-V1".into(),
        };
        let v: serde_json::Value = serde_json::from_str(&s.to_json()).unwrap();
        let mut keys: Vec<&str> = v.as_object().unwrap().keys().map(String::as_str).collect();
        keys.sort_unstable();
        let mut want: Vec<&str> = SIDECAR_FIELDS.iter().map(|(k, _)| *k).collect();
        want.sort_unstable();
        assert_eq!(keys, want, "exactly the nine fields");
        let text = s.to_json();
        let pos: Vec<usize> = SIDECAR_FIELDS.iter().map(|(k, _)| text.find(&format!("\"{k}\"")).unwrap()).collect();
        assert!(pos.windows(2).all(|w| w[0] < w[1]), "fields written in programme order");
    }
}
