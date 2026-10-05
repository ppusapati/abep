//! Hash-verified reader of the frozen intake surface v1 (`abep_sim/data/intake_surface_v1.{csv,json}`, CLAUDE.md
//! rule 1: read, never regenerated) and of the captured reference triangulation of its grid
//! (`crates/abep-intake/data/intake_surface_v1_delaunay_v1.json`).
//!
//! Kept inside abep-intake until the shared frozen-data crate (abep-data, lane B1) exists.

use abep_provenance::read_verified;
use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use std::path::Path;

pub const SURFACE_V1_CSV: &str = "abep_sim/data/intake_surface_v1.csv";
pub const SURFACE_V1_CSV_SHA256: &str = "62b804924d801f913420a05142d4fe62137a7619eca17ae7786da5bef005c09a";
pub const SURFACE_V1_JSON: &str = "abep_sim/data/intake_surface_v1.json";
pub const SURFACE_V1_JSON_SHA256: &str = "5b26b7fd60272537dd0e719a122cb874233c6dd777202ab164b159cc7215d425";
pub const TRIANGULATION_V1: &str = "crates/abep-intake/data/intake_surface_v1_delaunay_v1.json";
pub const TRIANGULATION_V1_SHA256: &str = "247601cf51cff450759a2148179242e8085eb8fb0b878d87e44ea86e644faf7b";

/// Columns of intake_surface_v1.csv, in file order.
pub const CSV_COLUMNS: [&str; 16] = [
    "eta_c",
    "C_D",
    "K_back",
    "CR_passive",
    "eta_open",
    "unresolved_fraction",
    "converged",
    "scattering",
    "mean_wall_hits",
    "mass_kg",
    "alpha",
    "theta_deg",
    "L_over_d",
    "phi",
    "d_mm",
    "species",
];

/// One row of the frozen surface (the fields the surface uses).
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceRow {
    pub eta_c: f64,
    pub c_d: f64,
    pub k_back: f64,
    pub cr_passive: f64,
    pub unresolved_fraction: f64,
    pub mass_kg: f64,
    pub alpha: f64,
    pub theta_deg: f64,
    pub l_over_d: f64,
    pub phi: f64,
    pub scattering: String,
    pub species: String,
}

fn schema(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: message.into() }
}

fn num(path: &str, line: usize, col: &str, s: &str) -> AbepResult<f64> {
    s.parse::<f64>().map_err(|e| schema(path, format!("line {line}, column {col}: {s:?} is not a number ({e})")))
}

/// Read and parse the frozen CSV (sha256-verified). Floats parse correctly rounded (contract DIV-05).
pub fn read_surface_v1(repo_root: &Path) -> AbepResult<Vec<SurfaceRow>> {
    let bytes = read_verified(&repo_root.join(SURFACE_V1_CSV), SURFACE_V1_CSV_SHA256)?;
    // the metadata travels with the table: verified on the same load
    let meta = read_verified(&repo_root.join(SURFACE_V1_JSON), SURFACE_V1_JSON_SHA256)?;
    let meta: serde_json::Value = serde_json::from_slice(&meta).map_err(|e| schema(SURFACE_V1_JSON, e.to_string()))?;
    if meta["sha256_16"].as_str() != Some(&SURFACE_V1_CSV_SHA256[..16]) {
        return Err(schema(SURFACE_V1_JSON, "sha256_16 does not match the CSV"));
    }
    let text = std::str::from_utf8(&bytes).map_err(|e| schema(SURFACE_V1_CSV, e.to_string()))?;
    let mut lines = text.lines();
    let header: Vec<&str> = lines.next().ok_or_else(|| schema(SURFACE_V1_CSV, "empty file"))?.split(',').collect();
    if header != CSV_COLUMNS {
        return Err(schema(SURFACE_V1_CSV, format!("header {header:?}")));
    }
    let mut rows = Vec::new();
    for (i, line) in lines.enumerate() {
        let f: Vec<&str> = line.split(',').collect();
        if f.len() != CSV_COLUMNS.len() {
            return Err(schema(SURFACE_V1_CSV, format!("line {}: {} fields", i + 2, f.len())));
        }
        let g = |k: usize| num(SURFACE_V1_CSV, i + 2, CSV_COLUMNS[k], f[k]);
        rows.push(SurfaceRow {
            eta_c: g(0)?,
            c_d: g(1)?,
            k_back: g(2)?,
            cr_passive: g(3)?,
            unresolved_fraction: g(5)?,
            mass_kg: g(9)?,
            alpha: g(10)?,
            theta_deg: g(11)?,
            l_over_d: g(12)?,
            phi: g(13)?,
            scattering: f[7].to_string(),
            species: f[15].to_string(),
        });
    }
    Ok(rows)
}

/// The captured reference triangulation (schema `abep_intake_surface_triangulation_v1`).
#[derive(Debug, Clone, Deserialize)]
pub struct Triangulation {
    pub schema: String,
    pub frozen_surface: FrozenRef,
    pub axes: Vec<String>,
    pub points: Vec<[f64; 4]>,
    pub rescale: Rescale,
    pub simplices: Vec<[usize; 5]>,
    pub degenerate: Vec<bool>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct FrozenRef {
    pub csv_sha256: String,
    pub json_sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Rescale {
    pub offset: [f64; 4],
    pub scale: [f64; 4],
}

/// Read the captured triangulation (sha256-verified) and check it refers to the frozen v1 files.
pub fn read_triangulation_v1(repo_root: &Path) -> AbepResult<Triangulation> {
    let bytes = read_verified(&repo_root.join(TRIANGULATION_V1), TRIANGULATION_V1_SHA256)?;
    let t: Triangulation = serde_json::from_slice(&bytes).map_err(|e| schema(TRIANGULATION_V1, e.to_string()))?;
    if t.schema != "abep_intake_surface_triangulation_v1"
        || t.frozen_surface.csv_sha256 != SURFACE_V1_CSV_SHA256
        || t.frozen_surface.json_sha256 != SURFACE_V1_JSON_SHA256
        || t.axes != ["L_over_d", "phi", "alpha", "theta_deg"]
        || t.simplices.len() != t.degenerate.len()
    {
        return Err(schema(TRIANGULATION_V1, "schema, axes or frozen-surface binding mismatch"));
    }
    if t.simplices.iter().flatten().any(|&k| k >= t.points.len()) {
        return Err(schema(TRIANGULATION_V1, "simplex vertex index out of range"));
    }
    Ok(t)
}

pub const SEARCH_V1: &str = "crates/abep-intake/data/intake_surface_v1_delaunay_v1_search.json";
pub const SEARCH_V1_SHA256: &str = "e6f254b3f089123b2c8eadaac7adf66b6d64f823540a4ed8cb4d86cba301b3fd";

/// scipy Delaunay search structures of the captured triangulation (schema `abep_intake_surface_delaunay_search_v1`):
/// what `Delaunay.find_simplex` / `LinearNDInterpolator` use to choose the containing simplex.
#[derive(Debug, Clone, Deserialize)]
pub struct SearchStructures {
    pub schema: String,
    pub triangulation: FileRef,
    /// per simplex: rows 0..3 = barycentric transform, row 4 = rescaled last vertex; None = degenerate
    pub transform: Vec<Option<[[f64; 4]; 5]>>,
    pub neighbors: Vec<[i64; 5]>,
    pub equations: Vec<[f64; 6]>,
    pub paraboloid_scale: f64,
    pub paraboloid_shift: f64,
    pub min_bound: [f64; 4],
    pub max_bound: [f64; 4],
}

#[derive(Debug, Clone, Deserialize)]
pub struct FileRef {
    pub path: String,
    pub sha256: String,
}

/// Read the captured search structures (sha256-verified) and check they belong to the captured triangulation.
pub fn read_search_v1(repo_root: &Path, n_simplices: usize) -> AbepResult<SearchStructures> {
    let bytes = read_verified(&repo_root.join(SEARCH_V1), SEARCH_V1_SHA256)?;
    let s: SearchStructures = serde_json::from_slice(&bytes).map_err(|e| schema(SEARCH_V1, e.to_string()))?;
    if s.schema != "abep_intake_surface_delaunay_search_v1"
        || s.triangulation.path != TRIANGULATION_V1
        || s.triangulation.sha256 != TRIANGULATION_V1_SHA256
        || s.transform.len() != n_simplices
        || s.neighbors.len() != n_simplices
        || s.equations.len() != n_simplices
    {
        return Err(schema(SEARCH_V1, "schema, triangulation binding or array length mismatch"));
    }
    if s.neighbors.iter().flatten().any(|&k| k < -1 || k >= n_simplices as i64) {
        return Err(schema(SEARCH_V1, "neighbor index out of range"));
    }
    Ok(s)
}
