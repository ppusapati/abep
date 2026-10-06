//! `atmosphere_msis21_orbit_v1`: the orbit-resolved frozen NRLMSIS 2.1 grid (reference
//! `abep_sim/atmosphere_orbit.py::load`; A9.13 S6.14, A9.14 S9.7 / S9.8, A9.17 DATA_SIZE). Four discrete ECSS-E-ST-10-04C
//! Rev.1 Table 6-3 driver scenarios; grid alt x lat x LST x lon x doy; one canonical deterministic-gzip CSV.

use crate::gz::read_container;
use crate::json::OValue;
use crate::pins::FrozenPins;
use crate::table::{check_header, lines, parse_f64, schema};
use crate::{data_path, data_rel};
use abep_provenance::sha256_hex;
use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use std::path::Path;

pub const DATASET_ID: &str = "atmosphere_msis21_orbit_v1";
pub const GZ_FILE: &str = "atmosphere_msis21_orbit_v1.csv.gz";
pub const LEGACY_CSV_FILE: &str = "atmosphere_msis21_orbit_v1.csv";
pub const JSON_FILE: &str = "atmosphere_msis21_orbit_v1.json";
pub const DESIGN_V1_FILE: &str = "atmosphere_msis21_orbit_v1_design_states.json";
pub const DESIGN_V2_FILE: &str = "atmosphere_msis21_orbit_v1_design_states_v2.json";

pub const ALT_KM: [f64; 4] = [180.0, 195.0, 215.0, 230.0];
pub const LAT_DEG: [f64; 19] = [
    -90.0, -80.0, -70.0, -60.0, -50.0, -40.0, -30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0,
    90.0,
];
pub const LST_H: [f64; 8] = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0];
pub const LON_DEG: [f64; 6] = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0];
pub const DOY_PERIOD: f64 = 365.0;
pub const DOY_M: usize = 8;
/// Integer MSIS days nearest to 1 + k * 365/8.
pub const DOY: [f64; 8] = [1.0, 47.0, 92.0, 138.0, 184.0, 229.0, 275.0, 320.0];
/// Grid shape per scenario: (doy, alt, lat, lon, lst).
pub const SHAPE: [usize; 5] = [8, 4, 19, 6, 8];
pub const N_PER_SCENARIO: usize = 8 * 4 * 19 * 6 * 8;

/// A discrete ECSS driver scenario (verbatim ECSS-E-ST-10-04C Rev.1 Table 6-3).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Scenario {
    pub id: &'static str,
    pub f107: f64,
    pub f107a: f64,
    pub ap: f64,
}

pub const SCENARIOS: [Scenario; 4] = [
    Scenario { id: "ECSS_LT_LOW", f107: 65.0, f107a: 65.0, ap: 0.0 },
    Scenario { id: "ECSS_LT_MODERATE", f107: 140.0, f107a: 140.0, ap: 15.0 },
    Scenario { id: "ECSS_LT_HIGH", f107: 250.0, f107a: 250.0, ap: 45.0 },
    Scenario { id: "ECSS_ST_HIGH", f107: 300.0, f107a: 250.0, ap: 240.0 },
];
pub const NOMINAL_SCENARIO: &str = "ECSS_LT_MODERATE";

/// Index of a scenario id in `SCENARIOS` (no driver interpolation: unknown ids are `None`).
pub fn scenario_index(id: &str) -> Option<usize> {
    SCENARIOS.iter().position(|s| s.id == id)
}

/// Stored species, in column order.
pub const SPECIES: [&str; 6] = ["N2", "O2", "O", "He", "Ar", "N"];
/// Output columns: rho, n_N2, n_O2, n_O, n_He, n_Ar, n_N, T.
pub const N_OUT: usize = 8;
pub const COLUMNS: [&str; 18] = [
    "scenario",
    "f107",
    "f107a",
    "ap",
    "doy",
    "alt_km",
    "lat_deg",
    "lon_deg",
    "lst_h",
    "ut_h",
    "rho_kg_m3",
    "n_N2_m3",
    "n_O2_m3",
    "n_O_m3",
    "n_He_m3",
    "n_Ar_m3",
    "n_N_m3",
    "T_K",
];

#[derive(Debug, Clone, Deserialize)]
pub struct Container {
    pub sha256: String,
    pub bytes: Option<u64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CheckSubset {
    pub stride: usize,
    pub n_rows: usize,
    pub sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct FileRecord {
    pub file: Option<String>,
    pub sha256: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Axes {
    pub alt_km: Vec<f64>,
    pub lat_deg: Vec<f64>,
    pub lst_h: Vec<f64>,
    pub lon_deg: Vec<f64>,
    pub doy: Vec<f64>,
}

/// The sidecar fields the readers use (the full document is kept as `doc`).
#[derive(Debug, Clone)]
pub struct OrbitV1Meta {
    pub sha256: String,
    pub bytes: u64,
    pub row_count: u64,
    pub grid: Axes,
    pub container: Container,
    pub check_subset: CheckSubset,
    pub design_states_file: Option<FileRecord>,
    pub doc: OValue,
}

impl OrbitV1Meta {
    pub fn parse(bytes: &[u8], path: &str) -> AbepResult<OrbitV1Meta> {
        #[derive(Deserialize)]
        struct M {
            sha256: String,
            bytes: u64,
            row_count: u64,
            grid: Axes,
            container: Container,
            check_subset: CheckSubset,
            design_states_file: Option<FileRecord>,
        }
        let m: M = serde_json::from_slice(bytes).map_err(|e| schema(path, e.to_string()))?;
        Ok(OrbitV1Meta {
            sha256: m.sha256,
            bytes: m.bytes,
            row_count: m.row_count,
            grid: m.grid,
            container: m.container,
            check_subset: m.check_subset,
            design_states_file: m.design_states_file,
            doc: OValue::parse(bytes, path)?,
        })
    }

    /// `interpolation_validation.by_scenario[scenario].rho_kg_m3.max_abs_rel` (None when absent).
    pub fn interp_max_rel_err_rho(&self, scenario: &str) -> Option<f64> {
        self.doc
            .get("interpolation_validation")?
            .get("by_scenario")?
            .get(scenario)?
            .get("rho_kg_m3")?
            .get("max_abs_rel")?
            .as_f64()
    }

    /// `design_states_file_v2` record (None when absent or null).
    pub fn design_states_file_v2(&self) -> Option<&OValue> {
        self.doc.get("design_states_file_v2").filter(|v| !matches!(v, OValue::Null))
    }
}

/// The loaded, verified grid.
#[derive(Debug, Clone)]
pub struct OrbitV1Data {
    pub meta: OrbitV1Meta,
    pub json_sha256: String,
    pub container_sha256: String,
    /// Per scenario (SCENARIOS order): N_PER_SCENARIO x N_OUT values, row-major (doy, alt, lat, lon, lst, column).
    pub grid: Vec<Vec<f64>>,
}

fn axes_match(meta: &Axes) -> bool {
    meta.alt_km == ALT_KM
        && meta.lat_deg == LAT_DEG
        && meta.lst_h == LST_H
        && meta.lon_deg == LON_DEG
        && meta.doy == DOY
}

/// Canonical (doy, alt, lat, lon, lst) key of flat row index `i` within a scenario block.
pub fn row_key(i: usize) -> [f64; 5] {
    let lst = i % 8;
    let lon = (i / 8) % 6;
    let lat = (i / 48) % 19;
    let alt = (i / 912) % 4;
    let doy = i / 3648;
    [DOY[doy], ALT_KM[alt], LAT_DEG[lat], LON_DEG[lon], LST_H[lst]]
}

pub fn missing_data_error(repo_root: &Path) -> AbepError {
    AbepError::Io {
        path: data_path(repo_root, GZ_FILE).display().to_string(),
        message: format!(
            "{DATASET_ID} data files are not present (repository evidence, A9.17 DATA_SIZE: {} + {JSON_FILE}); there is \
             no fallback dataset",
            data_rel(GZ_FILE)
        ),
    }
}

/// Load the sidecar (pinned by the model set and the design-state set reference).
pub fn load_meta(repo_root: &Path, pins: &FrozenPins) -> AbepResult<(OrbitV1Meta, String)> {
    let rel = data_rel(JSON_FILE);
    let bytes = pins.read_pinned(repo_root, &rel, &[&pins.design_state_set_ref.manifest.sha256])?;
    Ok((OrbitV1Meta::parse(&bytes, &rel)?, sha256_hex(&bytes)))
}

/// `atmosphere_orbit.load(verify_hash=True)`, plus the configuration pins (DIV-D-01) and the per-row key check
/// (DIV-D-02).
pub fn load(repo_root: &Path, pins: &FrozenPins) -> AbepResult<OrbitV1Data> {
    if !(data_path(repo_root, GZ_FILE).exists() && data_path(repo_root, JSON_FILE).exists()) {
        return Err(missing_data_error(repo_root));
    }
    let (meta, json_sha256) = load_meta(repo_root, pins)?;
    let gz_rel = data_rel(GZ_FILE);
    let gz = pins.read_pinned(repo_root, &gz_rel, &[])?;
    if meta.sha256 != pins.design_state_set_ref.dataset_sha256 {
        return Err(AbepError::HashMismatch {
            path: data_rel(JSON_FILE),
            expected: pins.design_state_set_ref.dataset_sha256.clone(),
            actual: meta.sha256.clone(),
        });
    }
    let raw = read_container(&gz, &gz_rel, &meta.container.sha256, None, &meta.sha256)?;
    if !axes_match(&meta.grid) {
        return Err(schema(&data_rel(JSON_FILE), "grid axes differ from the module definition"));
    }
    let ls = lines(&raw, &gz_rel)?;
    let (header, body) = ls.split_first().ok_or_else(|| schema(&gz_rel, "empty CSV"))?;
    check_header(header, &COLUMNS, &gz_rel)?;
    if body.len() != N_PER_SCENARIO * SCENARIOS.len() {
        return Err(schema(&gz_rel, "row count does not match the grid"));
    }
    let mut grid = Vec::with_capacity(SCENARIOS.len());
    for (si, sc) in SCENARIOS.iter().enumerate() {
        let block = &body[si * N_PER_SCENARIO..(si + 1) * N_PER_SCENARIO];
        let mut g = Vec::with_capacity(N_PER_SCENARIO * N_OUT);
        for (i, line) in block.iter().enumerate() {
            let line_no = si * N_PER_SCENARIO + i + 2;
            let mut f = line.split(',');
            if f.next() != Some(sc.id) {
                return Err(schema(&gz_rel, format!("line {line_no}: scenario blocks out of order")));
            }
            let vals: Vec<&str> = f.collect();
            if vals.len() != COLUMNS.len() - 1 {
                return Err(schema(&gz_rel, format!("line {line_no}: field count")));
            }
            let key = row_key(i);
            for (k, kv) in key.iter().enumerate() {
                if parse_f64(vals[3 + k], &gz_rel, line_no)? != *kv {
                    return Err(schema(&gz_rel, format!("line {line_no}: row key differs from the canonical grid")));
                }
            }
            for v in &vals[9..] {
                let x = parse_f64(v, &gz_rel, line_no)?;
                if !x.is_finite() || x <= 0.0 {
                    return Err(schema(&gz_rel, "non-positive value in the frozen grid; log interpolation undefined"));
                }
                g.push(x);
            }
        }
        grid.push(g);
    }
    Ok(OrbitV1Data { meta, json_sha256, container_sha256: sha256_hex(&gz), grid })
}
