//! `atmosphere_msis21_hwm14_orbit_v2`: frozen HWM14 (HWM14.123114) neutral winds on the orbit-v1 grid plus the fine
//! DWM07 disturbance table (reference `abep_sim/atmosphere_orbit_v2.py::load`; A9.17 WINDS, status
//! DESIGN_ENVELOPE_PARAMETRIC). HWM14 itself is not a runtime dependency (A9.29 sec. 6): a missing or altered frozen
//! table is `MODEL_ERROR`, never a fallback to zero wind.

use crate::gz::read_container;
use crate::json::OValue;
use crate::orbit_v1::{self, Axes, OrbitV1Data, N_PER_SCENARIO, SCENARIOS};
use crate::pins::FrozenPins;
use crate::table::{check_header, lines, parse_f64, schema};
use crate::{data_path, data_rel};
use abep_provenance::sha256_hex;
use abep_types::{AbepError, AbepResult};
use serde::Deserialize;
use std::path::Path;

pub const DATASET_ID: &str = "atmosphere_msis21_hwm14_orbit_v2";
pub const DATASET_STATUS: &str = "DESIGN_ENVELOPE_PARAMETRIC";
pub const GZ_FILE: &str = "atmosphere_msis21_hwm14_orbit_v2.csv.gz";
pub const DIST_GZ_FILE: &str = "atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz";
pub const JSON_FILE: &str = "atmosphere_msis21_hwm14_orbit_v2.json";
pub const V1_CSV_SHA256: &str = "c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164";
pub const HWM14_VERSION: &str = "HWM14.123114";

pub const COLUMNS: [&str; 14] = [
    "scenario",
    "ap_hwm",
    "iyd",
    "doy",
    "alt_km",
    "lat_deg",
    "lon_deg",
    "lst_h",
    "ut_h",
    "ut_s",
    "u_mer_m_s",
    "u_zon_m_s",
    "u_mer_quiet_m_s",
    "u_zon_quiet_m_s",
];
pub const DIST_COLUMNS: [&str; 11] = [
    "scenario",
    "ap_hwm",
    "iyd",
    "doy",
    "alt_km",
    "lat_deg",
    "lon_deg",
    "lst_h",
    "ut_s",
    "u_mer_dist_m_s",
    "u_zon_dist_m_s",
];
pub const DIST_ALT_KM: f64 = 230.0;
/// Disturbance grid shape: (doy, lat, lon, lst).
pub const DIST_SHAPE: [usize; 4] = [8, 37, 24, 24];
pub const DIST_N_PER_SCENARIO: usize = 8 * 37 * 24 * 24;

pub fn dist_lat_deg() -> Vec<f64> {
    (0..37).map(|i| -90.0 + 5.0 * i as f64).collect()
}
pub fn dist_lon_deg() -> Vec<f64> {
    (0..24).map(|i| 15.0 * i as f64).collect()
}
pub fn dist_lst_h() -> Vec<f64> {
    (0..24).map(|i| i as f64).collect()
}

#[derive(Debug, Clone, Deserialize)]
struct Container {
    sha256: String,
}

#[derive(Debug, Clone, Deserialize)]
struct DistGrid {
    doy: Vec<f64>,
    lat_deg: Vec<f64>,
    lon_deg: Vec<f64>,
    lst_h: Vec<f64>,
}

#[derive(Debug, Clone, Deserialize)]
struct DistFile {
    sha256: String,
    container: Container,
    grid: DistGrid,
}

#[derive(Debug, Clone, Deserialize)]
struct Meta {
    sha256: String,
    container: Container,
    grid: Axes,
    disturbance_file: DistFile,
}

#[derive(Debug, Clone)]
pub struct WindV2Data {
    pub sha256: String,
    pub disturbance_sha256: String,
    pub json_sha256: String,
    pub doc: OValue,
    /// Per scenario: N_PER_SCENARIO x 2 quiet components (u_mer_quiet, u_zon_quiet), row-major (doy, alt, lat, lon,
    /// lst, component).
    pub quiet: Vec<Vec<f64>>,
    /// Per scenario: N_PER_SCENARIO x 2 stored total components (u_mer, u_zon) (provenance; not interpolated).
    pub total: Vec<Vec<f64>>,
    /// Per scenario: DIST_N_PER_SCENARIO x 2 disturbance components, row-major (doy, lat, lon, lst, component).
    pub dist: Vec<Vec<f64>>,
}

impl WindV2Data {
    /// `interpolation_validation.by_scenario[scenario].vector_total.max_abs` (None when absent).
    pub fn interp_max_abs_err(&self, scenario: &str) -> Option<f64> {
        self.doc
            .get("interpolation_validation")?
            .get("by_scenario")?
            .get(scenario)?
            .get("vector_total")?
            .get("max_abs")?
            .as_f64()
    }
}

fn missing(repo_root: &Path) -> AbepError {
    AbepError::Io {
        path: data_path(repo_root, GZ_FILE).display().to_string(),
        message: format!(
            "{DATASET_ID} data files are not present ({} + {DIST_GZ_FILE} + {JSON_FILE}); there is no fallback dataset",
            data_rel(GZ_FILE)
        ),
    }
}

fn dist_key(i: usize) -> [f64; 4] {
    let lst = i % 24;
    let lon = (i / 24) % 24;
    let lat = (i / 576) % 37;
    let doy = i / 21312;
    [orbit_v1::DOY[doy], -90.0 + 5.0 * lat as f64, 15.0 * lon as f64, lst as f64]
}

/// `atmosphere_orbit_v2.load(verify_hash=True)` given the loaded, verified v1 grid, plus the configuration pins.
pub fn load(repo_root: &Path, pins: &FrozenPins, v1: &OrbitV1Data) -> AbepResult<WindV2Data> {
    if ![GZ_FILE, DIST_GZ_FILE, JSON_FILE].iter().all(|f| data_path(repo_root, f).exists()) {
        return Err(missing(repo_root));
    }
    let json_rel = data_rel(JSON_FILE);
    let json_bytes = pins.read_pinned(repo_root, &json_rel, &[])?;
    let meta: Meta = serde_json::from_slice(&json_bytes).map_err(|e| schema(&json_rel, e.to_string()))?;
    let doc = OValue::parse(&json_bytes, &json_rel)?;
    let v1_ref = doc
        .get("composition")
        .and_then(|c| c.get("thermodynamic_state"))
        .and_then(|t| t.get("csv_sha256"))
        .and_then(|s| s.as_str());
    if v1_ref != Some(V1_CSV_SHA256) {
        return Err(schema(&json_rel, "v2 manifest does not reference the pinned v1 dataset"));
    }
    if v1.meta.sha256 != V1_CSV_SHA256 {
        return Err(AbepError::Model { message: "frozen v1 dataset differs from the one v2 was built on".into() });
    }
    let g = &meta.grid;
    if g.alt_km != orbit_v1::ALT_KM
        || g.lat_deg != orbit_v1::LAT_DEG
        || g.lst_h != orbit_v1::LST_H
        || g.lon_deg != orbit_v1::LON_DEG
        || g.doy != orbit_v1::DOY
    {
        return Err(schema(&json_rel, "grid axes differ from the v1 module definition"));
    }
    let dg = &meta.disturbance_file.grid;
    if dg.doy != orbit_v1::DOY
        || dg.lat_deg != dist_lat_deg()
        || dg.lon_deg != dist_lon_deg()
        || dg.lst_h != dist_lst_h()
    {
        return Err(schema(&json_rel, "disturbance grid axes differ from the module definition"));
    }

    let gz_rel = data_rel(GZ_FILE);
    let gz = pins.read_pinned(repo_root, &gz_rel, &[])?;
    let raw = read_container(&gz, &gz_rel, &meta.container.sha256, None, &meta.sha256)?;
    let ls = lines(&raw, &gz_rel)?;
    let (header, body) = ls.split_first().ok_or_else(|| schema(&gz_rel, "empty CSV"))?;
    check_header(header, &COLUMNS, &gz_rel)?;
    if body.len() != N_PER_SCENARIO * SCENARIOS.len() {
        return Err(schema(&gz_rel, "row count does not match the grid"));
    }

    let dist_rel = data_rel(DIST_GZ_FILE);
    let dgz = pins.read_pinned(repo_root, &dist_rel, &[])?;
    let draw =
        read_container(&dgz, &dist_rel, &meta.disturbance_file.container.sha256, None, &meta.disturbance_file.sha256)?;
    let dls = lines(&draw, &dist_rel)?;
    let (dheader, dbody) = dls.split_first().ok_or_else(|| schema(&dist_rel, "empty CSV"))?;
    check_header(dheader, &DIST_COLUMNS, &dist_rel)?;
    if dbody.len() != DIST_N_PER_SCENARIO * SCENARIOS.len() {
        return Err(schema(&dist_rel, "row count does not match the grid"));
    }

    let (mut quiet, mut total, mut dist) = (Vec::new(), Vec::new(), Vec::new());
    for (si, sc) in SCENARIOS.iter().enumerate() {
        let mut q = Vec::with_capacity(N_PER_SCENARIO * 2);
        let mut t = Vec::with_capacity(N_PER_SCENARIO * 2);
        for (i, line) in body[si * N_PER_SCENARIO..(si + 1) * N_PER_SCENARIO].iter().enumerate() {
            let line_no = si * N_PER_SCENARIO + i + 2;
            let f: Vec<&str> = line.split(',').collect();
            if f.len() != COLUMNS.len() || f[0] != sc.id {
                return Err(schema(&gz_rel, format!("line {line_no}: scenario blocks out of order or field count")));
            }
            let v: Vec<f64> = f[1..].iter().map(|x| parse_f64(x, &gz_rel, line_no)).collect::<AbepResult<_>>()?;
            let key = orbit_v1::row_key(i);
            if v[2..7] != key {
                return Err(schema(&gz_rel, "v2 row keys differ from the v1 grid (doy, alt, lat, lon, lst)"));
            }
            if v[0] != sc.ap {
                return Err(schema(&gz_rel, "ap column differs from the scenario ap"));
            }
            t.extend_from_slice(&v[9..11]);
            q.extend_from_slice(&v[11..13]);
        }
        let mut d = Vec::with_capacity(DIST_N_PER_SCENARIO * 2);
        for (i, line) in dbody[si * DIST_N_PER_SCENARIO..(si + 1) * DIST_N_PER_SCENARIO].iter().enumerate() {
            let line_no = si * DIST_N_PER_SCENARIO + i + 2;
            let f: Vec<&str> = line.split(',').collect();
            if f.len() != DIST_COLUMNS.len() || f[0] != sc.id {
                return Err(schema(&dist_rel, format!("line {line_no}: scenario blocks out of order or field count")));
            }
            let v: Vec<f64> = f[1..].iter().map(|x| parse_f64(x, &dist_rel, line_no)).collect::<AbepResult<_>>()?;
            let key = dist_key(i);
            if [v[2], v[4], v[5], v[6]] != key || v[3] != DIST_ALT_KM || v[0] != sc.ap {
                return Err(schema(
                    &dist_rel,
                    "disturbance-table row keys differ from the module grid / altitude / ap",
                ));
            }
            d.extend_from_slice(&v[8..10]);
        }
        quiet.push(q);
        total.push(t);
        dist.push(d);
    }
    Ok(WindV2Data {
        sha256: meta.sha256,
        disturbance_sha256: meta.disturbance_file.sha256,
        json_sha256: sha256_hex(&json_bytes),
        doc,
        quiet,
        total,
        dist,
    })
}
