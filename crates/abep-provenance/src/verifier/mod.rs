//! Generic provenance verifier (SC-WP-12, RM-OQ-09; contract
//! `docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_prereg_v1.json`).
//!
//! It re-implements the check semantics of `scripts/ci_checks.py` `verify_sha_map`, `check_prereg_lock`,
//! `check_audit_manifest`, `check_hallthruster_pin` and `check_h2_6_live_sources` (the H2-6 builder's
//! `verify_sources()`): sha256 pin maps read from the tree's own records, pinned owner decisions, consumed values
//! against their live sources, and HallThruster.jl pin consistency. Check-specific content is data: the pin maps live
//! in the tree, the live-source checks in a versioned spec (`docs/ci/provenance_specs/`).
//!
//! Every finding is an integrity violation (`MODEL_ERROR`). Where the Python check lets an exception escape, the Rust
//! check aborts with exactly one `RAISED` finding, as the Python problem list is lost with the exception. The verifier
//! never writes into the tree it verifies.

mod checks;
mod live_sources;
mod load;
mod pyliteral;
mod pyvalue;
mod sha_map;

pub use live_sources::{verify_live_sources, H2_6_SPEC_JSON, H2_6_SPEC_PATH, H2_6_SPEC_SHA256};
pub use pyvalue::PyValue;
pub use sha_map::verify_sha_map;

use abep_types::EvalStatus;
use serde::{Deserialize, Serialize};
use std::fmt;
use std::path::Path;

/// The checks this verifier implements, named as in `scripts/ci_checks.py`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum CheckName {
    #[serde(rename = "prereg_lock")]
    PreregLock,
    #[serde(rename = "audit_manifest")]
    AuditManifest,
    #[serde(rename = "hallthruster_pin")]
    HallthrusterPin,
    #[serde(rename = "h2_6_live_sources")]
    H26LiveSources,
}

impl CheckName {
    pub const ALL: [CheckName; 4] =
        [CheckName::PreregLock, CheckName::AuditManifest, CheckName::HallthrusterPin, CheckName::H26LiveSources];

    pub fn as_str(self) -> &'static str {
        match self {
            CheckName::PreregLock => "prereg_lock",
            CheckName::AuditManifest => "audit_manifest",
            CheckName::HallthrusterPin => "hallthruster_pin",
            CheckName::H26LiveSources => "h2_6_live_sources",
        }
    }

    pub fn parse(name: &str) -> Option<CheckName> {
        CheckName::ALL.into_iter().find(|c| c.as_str() == name)
    }
}

impl fmt::Display for CheckName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Finding kinds (contract `identity_schema.kinds`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FindingKind {
    /// A pinned file is absent.
    Missing,
    /// A pinned file's bytes differ from the recorded sha256.
    Sha256Mismatch,
    /// A pin record lists nothing.
    EmptyPinSet,
    /// A mandatory entry has no pin.
    Unpinned,
    /// Two registered sets differ.
    SetMismatch,
    /// A record has the wrong number of entries.
    EntryCount,
    /// A value differs from the value it must equal.
    ValueMismatch,
    /// A live source file is absent.
    SourceMissing,
    /// A live source lacks a key the check reads.
    SourceKeyMissing,
    /// The check aborted; `key` carries the raised class.
    Raised,
}

impl FindingKind {
    pub fn as_str(self) -> &'static str {
        match self {
            FindingKind::Missing => "MISSING",
            FindingKind::Sha256Mismatch => "SHA256_MISMATCH",
            FindingKind::EmptyPinSet => "EMPTY_PIN_SET",
            FindingKind::Unpinned => "UNPINNED",
            FindingKind::SetMismatch => "SET_MISMATCH",
            FindingKind::EntryCount => "ENTRY_COUNT",
            FindingKind::ValueMismatch => "VALUE_MISMATCH",
            FindingKind::SourceMissing => "SOURCE_MISSING",
            FindingKind::SourceKeyMissing => "SOURCE_KEY_MISSING",
            FindingKind::Raised => "RAISED",
        }
    }
}

/// One integrity violation. `(kind, file, key)` is its identity; `detail` is explanatory only.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Finding {
    pub kind: FindingKind,
    /// Repository-relative POSIX path (lexically normalised), or empty.
    pub file: String,
    pub key: String,
    pub detail: String,
}

impl Finding {
    pub(crate) fn new(
        kind: FindingKind,
        file: impl Into<String>,
        key: impl Into<String>,
        detail: impl Into<String>,
    ) -> Self {
        Finding { kind, file: file.into(), key: key.into(), detail: detail.into() }
    }

    /// Every finding is fail-closed.
    pub fn status(&self) -> EvalStatus {
        EvalStatus::ModelError
    }

    pub fn identity(&self) -> (FindingKind, &str, &str) {
        (self.kind, self.file.as_str(), self.key.as_str())
    }
}

/// Result of one check on one tree.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CheckReport {
    pub check: CheckName,
    /// `EVALUATED` when the check found nothing, `MODEL_ERROR` otherwise.
    pub status: EvalStatus,
    pub findings: Vec<Finding>,
    pub note: String,
}

impl CheckReport {
    pub fn verified(&self) -> bool {
        self.findings.is_empty()
    }

    fn from_outcome(check: CheckName, outcome: Result<(Vec<Finding>, String), Raised>) -> Self {
        let (findings, note) = match outcome {
            Ok(r) => r,
            Err(raised) => (vec![raised.into_finding()], String::new()),
        };
        let status = if findings.is_empty() { EvalStatus::Evaluated } else { EvalStatus::ModelError };
        CheckReport { check, status, findings, note }
    }
}

/// An error that escapes a check (Python: an exception reaching `run_checks`). The class names are the contract's
/// `identity_schema.raised_classes`.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum Raised {
    /// JSONDecodeError / TOMLDecodeError / UnicodeDecodeError.
    Decode { file: String, detail: String },
    /// FileNotFoundError outside a catching context.
    FileMissing { file: String },
    /// KeyError.
    KeyMissing { key: String },
    /// TypeError / AttributeError.
    Type { detail: String },
    /// ValueError.
    Value { detail: String },
    /// Any other exception class, by its Python name.
    Other { name: String, detail: String },
    /// Rust-only: a Python-literal target statement outside the supported grammar.
    UnsupportedSyntax { file: String, detail: String },
    /// Rust-only: the embedded spec or the consumed record is inconsistent.
    Spec { detail: String },
}

impl Raised {
    pub(crate) fn type_error(detail: impl Into<String>) -> Self {
        Raised::Type { detail: detail.into() }
    }

    pub(crate) fn key(key: impl Into<String>) -> Self {
        Raised::KeyMissing { key: key.into() }
    }

    pub(crate) fn class(&self) -> String {
        match self {
            Raised::Decode { .. } => "DECODE_ERROR".into(),
            Raised::FileMissing { .. } => "FILE_MISSING".into(),
            Raised::KeyMissing { key } => format!("KEY_MISSING:{key}"),
            Raised::Type { .. } => "TYPE_ERROR".into(),
            Raised::Value { .. } => "VALUE_ERROR".into(),
            Raised::Other { name, .. } => format!("OTHER:{name}"),
            Raised::UnsupportedSyntax { .. } => "UNSUPPORTED_SYNTAX".into(),
            Raised::Spec { .. } => "SPEC_ERROR".into(),
        }
    }

    pub(crate) fn into_finding(self) -> Finding {
        let key = self.class();
        match self {
            Raised::FileMissing { file } => {
                Finding::new(FindingKind::Raised, file.clone(), key, format!("{file}: no such file"))
            }
            Raised::Decode { file, detail } | Raised::UnsupportedSyntax { file, detail } => {
                Finding::new(FindingKind::Raised, "", key, format!("{file}: {detail}"))
            }
            Raised::KeyMissing { .. } => Finding::new(FindingKind::Raised, "", key, "missing key"),
            Raised::Type { detail }
            | Raised::Value { detail }
            | Raised::Other { detail, .. }
            | Raised::Spec { detail } => Finding::new(FindingKind::Raised, "", key, detail),
        }
    }
}

pub(crate) type Py<T> = Result<T, Raised>;

/// Run `checks` (in the given order) on the tree rooted at `root`.
pub fn run_checks(root: &Path, checks: &[CheckName]) -> Vec<CheckReport> {
    checks
        .iter()
        .map(|&check| {
            let outcome = match check {
                CheckName::PreregLock => checks::prereg_lock(root),
                CheckName::AuditManifest => checks::audit_manifest(root),
                CheckName::HallthrusterPin => checks::hallthruster_pin(root),
                CheckName::H26LiveSources => live_sources::h2_6_live_sources(root),
            };
            CheckReport::from_outcome(check, outcome)
        })
        .collect()
}

/// Lexical POSIX normalisation, as Python's `posixpath.normpath`.
pub(crate) fn normpath(path: &str) -> String {
    if path.is_empty() {
        return ".".into();
    }
    let absolute = path.starts_with('/');
    let mut parts: Vec<&str> = Vec::new();
    for comp in path.split('/') {
        match comp {
            "" | "." => {}
            ".." => {
                if parts.last().is_some_and(|p| *p != "..") {
                    parts.pop();
                } else if !absolute {
                    parts.push("..");
                }
            }
            c => parts.push(c),
        }
    }
    let joined = parts.join("/");
    match (absolute, joined.is_empty()) {
        (true, _) => format!("/{joined}"),
        (false, true) => ".".into(),
        (false, false) => joined,
    }
}

/// `posixpath.normpath(posixpath.join(base, rel))`: an absolute `rel` replaces `base`.
pub(crate) fn join_norm(base: &str, rel: &str) -> String {
    if rel.starts_with('/') || base.is_empty() {
        normpath(rel)
    } else {
        normpath(&format!("{base}/{rel}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normpath_matches_posixpath() {
        for (p, want) in [
            ("a/b/../c", "a/c"),
            ("./a//b/", "a/b"),
            ("../a", "../a"),
            ("a/../../b", "../b"),
            ("/a/../..", "/"),
            ("", "."),
            ("a/..", "."),
        ] {
            assert_eq!(normpath(p), want, "{p}");
        }
        assert_eq!(join_norm("hallthruster_bridge", "prereg/x.json"), "hallthruster_bridge/prereg/x.json");
        assert_eq!(join_norm("hallthruster_bridge/propellants", "../cases/p.json"), "hallthruster_bridge/cases/p.json");
        assert_eq!(join_norm("base", "/abs/x"), "/abs/x");
    }

    #[test]
    fn raised_classes_are_the_registered_vocabulary() {
        assert_eq!(Raised::Decode { file: "f".into(), detail: "d".into() }.class(), "DECODE_ERROR");
        assert_eq!(Raised::key("cases").class(), "KEY_MISSING:cases");
        assert_eq!(Raised::type_error("x").class(), "TYPE_ERROR");
        assert_eq!(
            Raised::Other { name: "IsADirectoryError".into(), detail: String::new() }.class(),
            "OTHER:IsADirectoryError"
        );
        let f = Raised::FileMissing { file: "a/b.json".into() }.into_finding();
        assert_eq!(f.identity(), (FindingKind::Raised, "a/b.json", "FILE_MISSING"));
        assert_eq!(f.status(), EvalStatus::ModelError);
    }

    #[test]
    fn check_names_round_trip() {
        for c in CheckName::ALL {
            assert_eq!(CheckName::parse(c.as_str()), Some(c));
            assert_eq!(serde_json::to_string(&c).unwrap(), format!("\"{c}\""));
        }
        assert_eq!(CheckName::parse("parse_json_toml"), None);
    }
}
