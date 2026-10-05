//! Provenance foundation: sha256 of bytes / files, repository-root discovery and verification of the configuration
//! manifest `config/MANIFEST.json` (schema `abep_config_manifest_v1`).
//!
//! CLAUDE.md rule 1: frozen data and configuration carry hashes and are verified on every load; a mismatch is a
//! `MODEL_ERROR`, never a warning (rule 3, no silent fallbacks).

pub mod bid_guard;
pub mod git;

use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// Lower-case hex sha256 of `bytes`.
pub fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

/// Read a file completely; I/O failures are `AbepError::Io`.
pub fn read_bytes(path: &Path) -> AbepResult<Vec<u8>> {
    std::fs::read(path).map_err(|e| AbepError::Io { path: path.display().to_string(), message: e.to_string() })
}

/// Lower-case hex sha256 of a file's bytes.
pub fn sha256_file(path: &Path) -> AbepResult<String> {
    Ok(sha256_hex(&read_bytes(path)?))
}

/// Read a file and check its sha256 against `expected` (lower-case hex). Returns the bytes only on a match.
pub fn read_verified(path: &Path, expected: &str) -> AbepResult<Vec<u8>> {
    let bytes = read_bytes(path)?;
    let actual = sha256_hex(&bytes);
    if actual != expected {
        return Err(AbepError::HashMismatch {
            path: path.display().to_string(),
            expected: expected.to_string(),
            actual,
        });
    }
    Ok(bytes)
}

/// Repository root: the nearest ancestor of `start` holding both `Cargo.toml` and `config/MANIFEST.json`.
pub fn find_repo_root(start: &Path) -> AbepResult<PathBuf> {
    let mut dir = Some(start);
    while let Some(d) = dir {
        if d.join("Cargo.toml").is_file() && d.join("config").join("MANIFEST.json").is_file() {
            return Ok(d.to_path_buf());
        }
        dir = d.parent();
    }
    Err(AbepError::Io {
        path: start.display().to_string(),
        message: "no ancestor holds Cargo.toml and config/MANIFEST.json".into(),
    })
}

/// Repository root resolved from this crate's manifest directory (tests and tools inside the workspace).
pub fn workspace_repo_root() -> AbepResult<PathBuf> {
    find_repo_root(Path::new(env!("CARGO_MANIFEST_DIR")))
}

/// One pinned file of `config/MANIFEST.json`.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct ManifestEntry {
    pub sha256: String,
    pub bytes: u64,
}

/// `config/MANIFEST.json` (schema `abep_config_manifest_v1`). Paths are relative to `config/`.
#[derive(Debug, Clone, Deserialize)]
pub struct ConfigManifest {
    pub schema: String,
    pub id: String,
    pub files: BTreeMap<String, ManifestEntry>,
}

pub const CONFIG_MANIFEST_SCHEMA: &str = "abep_config_manifest_v1";

impl ConfigManifest {
    /// Load `config/MANIFEST.json` under `repo_root`, refusing any other schema.
    pub fn load(repo_root: &Path) -> AbepResult<Self> {
        let path = repo_root.join("config").join("MANIFEST.json");
        let bytes = read_bytes(&path)?;
        let m: ConfigManifest = serde_json::from_slice(&bytes)
            .map_err(|e| AbepError::Schema { path: path.display().to_string(), message: e.to_string() })?;
        if m.schema != CONFIG_MANIFEST_SCHEMA {
            return Err(AbepError::Schema {
                path: path.display().to_string(),
                message: format!("schema {:?}, expected {CONFIG_MANIFEST_SCHEMA:?}", m.schema),
            });
        }
        Ok(m)
    }

    /// Read `config/<rel>` and verify it against its manifest entry (sha256 and byte count). A file absent from the
    /// manifest is refused: only pinned configuration may be loaded.
    pub fn read_verified(&self, repo_root: &Path, rel: &str) -> AbepResult<Vec<u8>> {
        let entry = self.files.get(rel).ok_or_else(|| AbepError::Schema {
            path: format!("config/{rel}"),
            message: "not pinned in config/MANIFEST.json".into(),
        })?;
        let path = repo_root.join("config").join(rel);
        let bytes = read_verified(&path, &entry.sha256)?;
        if bytes.len() as u64 != entry.bytes {
            return Err(AbepError::Schema {
                path: path.display().to_string(),
                message: format!("{} bytes, manifest pins {}", bytes.len(), entry.bytes),
            });
        }
        Ok(bytes)
    }

    /// Verify every pinned file. Returns the number verified or the first failure.
    pub fn verify_all(&self, repo_root: &Path) -> AbepResult<usize> {
        for rel in self.files.keys() {
            self.read_verified(repo_root, rel)?;
        }
        Ok(self.files.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_known_vectors() {
        assert_eq!(sha256_hex(b""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        assert_eq!(sha256_hex(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }
}
