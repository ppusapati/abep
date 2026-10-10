//! Canonical deterministic-gzip containers (A9.17 DATA_SIZE): the container sha256 identifies the stored file, the
//! uncompressed-CSV sha256 identifies the dataset; both are verified.

use abep_provenance::sha256_hex;
use abep_types::{AbepError, AbepResult};
use flate2::read::MultiGzDecoder;
use std::io::Read;

/// Decompress `gz` (all members, as Python's `gzip.decompress`).
pub fn gunzip(gz: &[u8], path: &str) -> AbepResult<Vec<u8>> {
    let mut out = Vec::new();
    MultiGzDecoder::new(gz)
        .read_to_end(&mut out)
        .map_err(|e| AbepError::Schema { path: path.to_string(), message: format!("gzip decode: {e}") })?;
    Ok(out)
}

/// Verify the container bytes against `container_sha256` (and `container_bytes` when given), decompress, and
/// verify the uncompressed bytes against `csv_sha256`.
pub fn read_container(
    gz: &[u8],
    path: &str,
    container_sha256: &str,
    container_bytes: Option<u64>,
    csv_sha256: &str,
) -> AbepResult<Vec<u8>> {
    let actual = sha256_hex(gz);
    if actual != container_sha256 {
        return Err(AbepError::HashMismatch { path: path.to_string(), expected: container_sha256.to_string(), actual });
    }
    if let Some(n) = container_bytes {
        if gz.len() as u64 != n {
            return Err(AbepError::Schema {
                path: path.to_string(),
                message: format!("{} container bytes, sidecar records {n}", gz.len()),
            });
        }
    }
    let raw = gunzip(gz, path)?;
    let raw_sha = sha256_hex(&raw);
    if raw_sha != csv_sha256 {
        return Err(AbepError::HashMismatch {
            path: format!("{path} (uncompressed CSV)"),
            expected: csv_sha256.to_string(),
            actual: raw_sha,
        });
    }
    Ok(raw)
}
