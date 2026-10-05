//! `abep_sim/data/atmosphere_msis21_v1.{csv,json}`: the frozen orbit-averaged NRLMSIS 2.1 scenario table (150-300 km
//! x F10.7 70..230, ap 15, epoch 2028-03-21T12:00), reference `abep_sim/atmosphere.py::_frozen`.

use crate::pins::FrozenPins;
use crate::table::{check_header, lines, parse_f64, schema};
use crate::{data_path, data_rel};
use abep_provenance::sha256_hex;
use abep_types::AbepResult;
use serde::Deserialize;
use std::path::Path;

pub const CSV_FILE: &str = "atmosphere_msis21_v1.csv";
pub const JSON_FILE: &str = "atmosphere_msis21_v1.json";
pub const COLUMNS: [&str; 7] = ["alt_km", "f107", "rho", "fO", "fN2", "fO2", "T"];

#[derive(Deserialize)]
struct Sidecar {
    file: String,
    sha256_16: String,
}

/// One F10.7 column of the table, sorted by altitude.
#[derive(Debug, Clone)]
pub struct F107Column {
    pub f107: f64,
    pub alt_km: Vec<f64>,
    pub rho: Vec<f64>,
    pub f_o: Vec<f64>,
    pub f_n2: Vec<f64>,
    pub f_o2: Vec<f64>,
    pub t_k: Vec<f64>,
}

#[derive(Debug, Clone)]
pub struct Msis21V1 {
    pub csv_sha256: String,
    pub json_sha256: String,
    /// Sidecar `sha256_16` (prefix of the CSV sha256), quoted in every result's `source`.
    pub sha256_16: String,
    /// Sorted unique altitudes over all rows (km).
    pub alt_axis: Vec<f64>,
    /// Sorted unique F10.7 values.
    pub f107_axis: Vec<f64>,
    /// One column per `f107_axis` entry.
    pub columns: Vec<F107Column>,
}

/// Load and verify the frozen table (model-set pins of the CSV and the JSON; the sidecar's `sha256_16` prefix).
pub fn load(repo_root: &Path, pins: &FrozenPins) -> AbepResult<Msis21V1> {
    let json_rel = data_rel(JSON_FILE);
    let json_bytes = pins.read_pinned(repo_root, &json_rel, &[])?;
    let side: Sidecar = serde_json::from_slice(&json_bytes).map_err(|e| schema(&json_rel, e.to_string()))?;
    if side.file != CSV_FILE || side.sha256_16.len() != 16 {
        return Err(schema(&json_rel, "sidecar file / sha256_16 fields"));
    }
    let csv_rel = data_rel(CSV_FILE);
    let csv = pins.read_pinned(repo_root, &csv_rel, &[])?;
    let csv_sha256 = sha256_hex(&csv);
    if !csv_sha256.starts_with(&side.sha256_16) {
        return Err(abep_types::AbepError::HashMismatch {
            path: data_path(repo_root, CSV_FILE).display().to_string(),
            expected: format!("{}... (sidecar sha256_16)", side.sha256_16),
            actual: csv_sha256,
        });
    }
    let ls = lines(&csv, &csv_rel)?;
    let (header, body) = ls.split_first().ok_or_else(|| schema(&csv_rel, "empty file"))?;
    check_header(header, &COLUMNS, &csv_rel)?;
    let mut rows: Vec<[f64; 7]> = Vec::with_capacity(body.len());
    for (i, line) in body.iter().enumerate() {
        let mut r = [0.0; 7];
        let mut n = 0;
        for (k, field) in line.split(',').enumerate() {
            if k >= 7 {
                return Err(schema(&csv_rel, format!("line {}: too many fields", i + 2)));
            }
            r[k] = parse_f64(field, &csv_rel, i + 2)?;
            n += 1;
        }
        if n != 7 || r.iter().any(|v| !v.is_finite()) || r[2] <= 0.0 {
            return Err(schema(&csv_rel, format!("line {}: 7 finite fields with rho > 0 required", i + 2)));
        }
        rows.push(r);
    }
    if rows.is_empty() {
        return Err(schema(&csv_rel, "no rows"));
    }
    let mut alt_axis: Vec<f64> = rows.iter().map(|r| r[0]).collect();
    alt_axis.sort_by(f64::total_cmp);
    alt_axis.dedup();
    let mut f107_axis: Vec<f64> = rows.iter().map(|r| r[1]).collect();
    f107_axis.sort_by(f64::total_cmp);
    f107_axis.dedup();
    if f107_axis.len() < 2 {
        return Err(schema(&csv_rel, "fewer than two F10.7 values"));
    }
    let mut columns = Vec::with_capacity(f107_axis.len());
    for &f in &f107_axis {
        let mut sel: Vec<&[f64; 7]> = rows.iter().filter(|r| r[1] == f).collect();
        sel.sort_by(|a, b| a[0].total_cmp(&b[0]));
        if sel.windows(2).any(|w| w[0][0] == w[1][0]) {
            return Err(schema(&csv_rel, format!("duplicate altitude in the F10.7 {f} column")));
        }
        columns.push(F107Column {
            f107: f,
            alt_km: sel.iter().map(|r| r[0]).collect(),
            rho: sel.iter().map(|r| r[2]).collect(),
            f_o: sel.iter().map(|r| r[3]).collect(),
            f_n2: sel.iter().map(|r| r[4]).collect(),
            f_o2: sel.iter().map(|r| r[5]).collect(),
            t_k: sel.iter().map(|r| r[6]).collect(),
        });
    }
    Ok(Msis21V1 {
        csv_sha256,
        json_sha256: sha256_hex(&json_bytes),
        sha256_16: side.sha256_16,
        alt_axis,
        f107_axis,
        columns,
    })
}
