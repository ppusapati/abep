//! `verify_sha_map`: every `{path relative to base_dir: sha256}` entry exists and matches.

use super::load::{abs_path, is_file, sha256_of};
use super::pyvalue::PyValue;
use super::{join_norm, Finding, FindingKind, Py, Raised};
use std::path::Path;

/// Verify a pin map (`pins.items()`, so `pins` must be a dict) under `base_rel` (repository-relative). Findings carry
/// the normalised repository-relative path and `label` as key. `Err` is the single RAISED finding of an aborted map.
pub fn verify_sha_map(root: &Path, base_rel: &str, pins: &PyValue, label: &str) -> Result<Vec<Finding>, Finding> {
    verify_pins(root, base_rel, pins, label).map_err(Raised::into_finding)
}

pub(crate) fn verify_pins(root: &Path, base_rel: &str, pins: &PyValue, label: &str) -> Py<Vec<Finding>> {
    verify_pairs(root, base_rel, &pins.items()?, label)
}

pub(crate) fn verify_pairs(root: &Path, base_rel: &str, pairs: &[(PyValue, PyValue)], label: &str) -> Py<Vec<Finding>> {
    let mut bad = Vec::new();
    for (rel, want) in pairs {
        let rel = match rel {
            PyValue::Str(s) => s,
            other => {
                return Err(Raised::type_error(format!(
                    "join() argument must be str, bytes, or os.PathLike object, not '{}'",
                    other.type_name()
                )))
            }
        };
        let file = join_norm(base_rel, rel);
        let path = if rel.starts_with('/') {
            Path::new(rel.as_str()).to_path_buf()
        } else {
            abs_path(root, base_rel).join(rel)
        };
        if !is_file(&path) {
            bad.push(Finding::new(FindingKind::Missing, file, label, format!("{label}: {rel} is missing")));
            continue;
        }
        let got = sha256_of(&path, &file)?;
        let matches = matches!(want, PyValue::Str(w) if *w == got);
        if !matches {
            bad.push(Finding::new(
                FindingKind::Sha256Mismatch,
                file,
                label,
                format!(
                    "{label}: {rel} sha256 {}... != pinned {}...",
                    &got[..16],
                    want.py_str().chars().take(16).collect::<String>()
                ),
            ));
        }
    }
    Ok(bad)
}
