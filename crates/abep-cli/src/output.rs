//! Result record (`abep_cli_result_v1`), run-record sidecar (`abep_cli_run_sidecar_v1`), and the registered exit codes
//! (acceptance_v2 `outputs`, `status_and_exit_codes`).
//!
//! The result record has one top-level key per line in a fixed order, each value compact JSON, and the payload spliced
//! verbatim in the owning crate's own serialization. The envelope adds no time stamp, host name, absolute path or
//! thread count, so identical inputs give identical bytes.

use crate::registry::ComponentState;
use abep_provenance::run_record::{DesignStateSet, HashedFile, RunRecord};
use abep_provenance::sha256_hex;
use abep_types::EvalStatus;
use serde::Serialize;
use std::path::{Path, PathBuf};

pub const RESULT_SCHEMA: &str = "abep_cli_result_v1";
pub const SIDECAR_SCHEMA: &str = "abep_cli_run_sidecar_v1";
/// The acceptance record that governs this binary.
pub const CONTRACT_ID: &str = "ACCEPT-NI-ABEP-CLI-V2";

pub const EXIT_EVALUATED: u8 = 0;
pub const EXIT_USAGE: u8 = 2;
pub const EXIT_UNREGISTERED_INPUT: u8 = 3;
pub const EXIT_PROVENANCE: u8 = 4;
pub const EXIT_OUTPUT_LOCATION: u8 = 5;
pub const EXIT_OUTPUT_WRITE: u8 = 6;

/// Registered exit code of a status.
pub fn exit_of(status: EvalStatus) -> u8 {
    match status {
        EvalStatus::Evaluated => EXIT_EVALUATED,
        EvalStatus::NotEvaluated => 10,
        EvalStatus::IncompleteEvidence => 11,
        EvalStatus::OutOfDomain => 12,
        EvalStatus::ModelError => 13,
    }
}

/// Severity for summarising several statuses: MODEL_ERROR > OUT_OF_DOMAIN > INCOMPLETE_EVIDENCE > NOT_EVALUATED >
/// EVALUATED.
pub fn severity(status: EvalStatus) -> u8 {
    match status {
        EvalStatus::Evaluated => 0,
        EvalStatus::NotEvaluated => 1,
        EvalStatus::IncompleteEvidence => 2,
        EvalStatus::OutOfDomain => 3,
        EvalStatus::ModelError => 4,
    }
}

/// The most severe of `statuses` (EVALUATED for none).
pub fn worst(statuses: impl IntoIterator<Item = EvalStatus>) -> EvalStatus {
    statuses.into_iter().max_by_key(|s| severity(*s)).unwrap_or(EvalStatus::Evaluated)
}

/// Parse a repository status string; anything outside the vocabulary is None.
pub fn parse_status(s: &str) -> Option<EvalStatus> {
    serde_json::from_value(serde_json::Value::String(s.to_string())).ok()
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Reason {
    pub code: String,
    pub message: String,
}

impl Reason {
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        Reason { code: code.to_string(), message: message.into() }
    }
}

/// The payload text and its serializer.
#[derive(Debug, Clone, PartialEq)]
pub struct Payload {
    /// `serde_json` | `python_json`
    pub format: &'static str,
    pub text: String,
}

impl Payload {
    pub fn serde<T: Serialize>(v: &T) -> Result<Payload, String> {
        serde_json::to_string(v).map(|text| Payload { format: "serde_json", text }).map_err(|e| e.to_string())
    }

    pub fn python(text: String) -> Payload {
        Payload { format: "python_json", text }
    }
}

/// The four governing hashes, as the run record captured and verified them.
#[derive(Debug, Clone, Serialize)]
pub struct GoverningHashes {
    pub config_manifest: HashedFile,
    pub architecture: HashedFile,
    pub model_set: HashedFile,
    pub design_state_set: DesignStateSet,
}

impl GoverningHashes {
    pub fn of(r: &RunRecord) -> Self {
        GoverningHashes {
            config_manifest: r.config_manifest.clone(),
            architecture: r.architecture.clone(),
            model_set: r.model_set.clone(),
            design_state_set: r.design_state_set.clone(),
        }
    }
}

/// Everything a result record states besides the command identity.
#[derive(Debug, Clone)]
pub struct Outcome {
    pub status: EvalStatus,
    pub exit: u8,
    pub reason: Option<Reason>,
    pub payload: Option<Payload>,
}

impl Outcome {
    /// An outcome whose exit code is the status's registered code.
    pub fn status(status: EvalStatus, reason: Option<Reason>, payload: Option<Payload>) -> Self {
        Outcome { status, exit: exit_of(status), reason, payload }
    }

    pub fn evaluated(payload: Payload) -> Self {
        Self::status(EvalStatus::Evaluated, None, Some(payload))
    }

    /// A crate error, reported verbatim with its fail-closed status and no payload.
    pub fn crate_error(status: EvalStatus, message: impl Into<String>) -> Self {
        let status = if status.is_evaluated() { EvalStatus::ModelError } else { status };
        Self::status(status, Some(Reason::new("CRATE_ERROR", message)), None)
    }

    /// Summary status of a command with a payload: EVALUATED, or a fail-closed status with its reason.
    pub fn summarised(status: EvalStatus, code: &str, message: impl Into<String>, payload: Payload) -> Self {
        if status.is_evaluated() {
            Self::evaluated(payload)
        } else {
            Self::status(status, Some(Reason::new(code, message)), Some(payload))
        }
    }
}

/// Command identity and provenance of a result record.
pub struct Header<'a> {
    pub command: &'a str,
    pub arguments: &'a [(&'static str, crate::args::ArgValue)],
    pub run_record: Option<&'a RunRecord>,
    pub components: &'a [ComponentState],
}

fn js<T: Serialize + ?Sized>(v: &T) -> String {
    serde_json::to_string(v).expect("the envelope always serializes")
}

fn arguments_json(args: &[(&'static str, crate::args::ArgValue)]) -> String {
    let items: Vec<String> = args
        .iter()
        .map(|(k, v)| {
            let val = match v {
                crate::args::ArgValue::Str(s) => js(s),
                crate::args::ArgValue::Num(x) => js(x),
            };
            format!("{}:{val}", js(k))
        })
        .collect();
    format!("{{{}}}", items.join(","))
}

/// The result record text.
pub fn result_text(h: &Header, o: &Outcome) -> String {
    let rr = h.run_record;
    let fields: Vec<(&str, String)> = vec![
        ("schema", js(RESULT_SCHEMA)),
        ("command", js(h.command)),
        ("arguments", arguments_json(h.arguments)),
        ("implementation", js("rust")),
        ("abep_cli_version", js(env!("CARGO_PKG_VERSION"))),
        ("rust_commit", js(&rr.map(|r| r.git_commit.as_str()))),
        ("git_dirty", js(&rr.map(|r| r.git_dirty))),
        ("rustc", js(abep_provenance::run_record::RUSTC_VERSION)),
        ("contract_id", js(CONTRACT_ID)),
        ("governing_hashes", js(&rr.map(GoverningHashes::of))),
        ("components", js(h.components)),
        ("status", js(&o.status)),
        ("exit_code", js(&o.exit)),
        ("reason", js(&o.reason)),
        ("payload_format", js(&o.payload.as_ref().map(|p| p.format))),
        ("payload", o.payload.as_ref().map_or_else(|| "null".to_string(), |p| p.text.trim_end().to_string())),
    ];
    let lines: Vec<String> = fields.iter().map(|(k, v)| format!("  {}: {v}", js(k))).collect();
    format!("{{\n{}\n}}\n", lines.join(",\n"))
}

#[derive(Debug, Clone, Serialize)]
pub struct Sidecar<'a> {
    pub schema: &'static str,
    pub command: &'a str,
    pub result_file: String,
    pub result_sha256: String,
    pub threads_requested: Option<usize>,
    pub threads_used: usize,
    pub run_record: &'a RunRecord,
}

pub fn sidecar_text(s: &Sidecar) -> String {
    let mut t = serde_json::to_string_pretty(s).expect("the sidecar always serializes");
    t.push('\n');
    t
}

pub fn result_path(out: &Path, stem: &str) -> PathBuf {
    out.join(format!("{stem}.result.json"))
}

pub fn sidecar_path(out: &Path, stem: &str) -> PathBuf {
    out.join(format!("{stem}.run_record.json"))
}

/// Write `text` to `path` through a temporary name in the same directory.
pub fn write_atomic(path: &Path, text: &str) -> Result<(), String> {
    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let tmp = path.with_file_name(format!(".{name}.tmp"));
    std::fs::write(&tmp, text).map_err(|e| format!("{}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, path).map_err(|e| format!("{}: {e}", path.display()))
}

pub fn sha256_text(text: &str) -> String {
    sha256_hex(text.as_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exit_codes_are_distinct_and_only_evaluated_is_zero() {
        let all = [
            EvalStatus::Evaluated,
            EvalStatus::NotEvaluated,
            EvalStatus::IncompleteEvidence,
            EvalStatus::OutOfDomain,
            EvalStatus::ModelError,
        ];
        let mut codes: Vec<u8> = all.iter().map(|s| exit_of(*s)).collect();
        codes.extend([EXIT_USAGE, EXIT_UNREGISTERED_INPUT, EXIT_PROVENANCE, EXIT_OUTPUT_LOCATION, EXIT_OUTPUT_WRITE]);
        let mut sorted = codes.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), codes.len());
        assert_eq!(codes.iter().filter(|c| **c == 0).count(), 1);
        assert_eq!(exit_of(EvalStatus::Evaluated), 0);
    }

    #[test]
    fn worst_follows_the_registered_severity() {
        use EvalStatus::*;
        assert_eq!(worst([]), Evaluated);
        assert_eq!(worst([Evaluated, NotEvaluated]), NotEvaluated);
        assert_eq!(worst([NotEvaluated, IncompleteEvidence, NotEvaluated]), IncompleteEvidence);
        assert_eq!(worst([IncompleteEvidence, OutOfDomain]), OutOfDomain);
        assert_eq!(worst([ModelError, OutOfDomain, Evaluated]), ModelError);
        assert_eq!(parse_status("INCOMPLETE_EVIDENCE"), Some(IncompleteEvidence));
        assert_eq!(parse_status("PASS"), None);
    }

    #[test]
    fn crate_error_is_never_evaluated() {
        assert_eq!(Outcome::crate_error(EvalStatus::Evaluated, "x").status, EvalStatus::ModelError);
        assert_eq!(Outcome::crate_error(EvalStatus::OutOfDomain, "x").exit, 12);
    }

    #[test]
    fn result_text_is_one_key_per_line_and_parses() {
        let h = Header { command: "hall status", arguments: &[], run_record: None, components: &[] };
        let o = Outcome::status(
            EvalStatus::NotEvaluated,
            Some(Reason::new("CRATE_STATUS", "m")),
            Some(Payload::python("{\"a\": NaN}".into())),
        );
        let t = result_text(&h, &o);
        assert!(t.starts_with("{\n  \"schema\": \"abep_cli_result_v1\",\n  \"command\": \"hall status\",\n"));
        assert!(t.ends_with("  \"payload\": {\"a\": NaN}\n}\n"));
        assert_eq!(t.lines().count(), 18);
        let v = abep_types::pyjson::loads(&t).unwrap();
        assert_eq!(v.as_dict().unwrap().get("exit_code").unwrap().to_f64().unwrap(), 10.0);
    }
}
