//! Orbit-resolved frozen NRLMSIS 2.1 atmosphere v1 (`abep_sim/atmosphere_orbit.py`: load, Domain, state, node_state,
//! orbit_states; contract PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1).
//!
//! Interpolation: natural log of every output column; separable weights in the order doy, alt, lat, lon, lst
//! (`weights`); scenarios are discrete (no driver interpolation); grid nodes are reproduced. Out-of-domain queries
//! are OUT_OF_DOMAIN (no extrapolation, no fallback).

use crate::mission_env_kernel::OMEGA_E;
use crate::pyfloat::{degrees, py_floordiv, py_format_g, py_int, py_mod, py_pow, radians, TWO_PI};
use crate::weights::{axis_weights, Axis};
use abep_data::orbit_v1::{
    self, scenario_index, OrbitV1Data, ALT_KM, DATASET_ID, DOY, LAT_DEG, LON_DEG, LST_H, N_OUT, SCENARIOS, SHAPE,
};
use abep_data::pins::FrozenPins;
use abep_types::constants::{MU_EARTH, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use std::path::Path;

/// `atmosphere_orbit.Domain` (closed intervals).
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct Domain {
    pub alt_km: (f64, f64),
    pub lat_deg: (f64, f64),
    pub lst_h: (f64, f64),
    pub lon_deg: (f64, f64),
    pub doy: (f64, f64),
}

pub const DOMAIN: Domain = Domain {
    alt_km: (ALT_KM[0], ALT_KM[3]),
    lat_deg: (-90.0, 90.0),
    lst_h: (0.0, 24.0),
    lon_deg: (-180.0, 360.0),
    doy: (1.0, 365.0),
};

/// `_check_domain`: a known scenario and finite coordinates inside DOMAIN; returns the scenario index.
pub fn check_domain(
    alt_km: f64,
    lat_deg: f64,
    lst_h: f64,
    lon_deg: f64,
    doy: f64,
    scenario: &str,
) -> AbepResult<usize> {
    let si = scenario_index(scenario).ok_or_else(|| AbepError::OutOfDomain {
        message: format!("scenario {scenario:?} is not in {DATASET_ID}; no driver interpolation"),
    })?;
    for (name, v, (lo, hi)) in [
        ("alt_km", alt_km, DOMAIN.alt_km),
        ("lat_deg", lat_deg, DOMAIN.lat_deg),
        ("lst_h", lst_h, DOMAIN.lst_h),
        ("lon_deg", lon_deg, DOMAIN.lon_deg),
        ("doy", doy, DOMAIN.doy),
    ] {
        if !v.is_finite() {
            return Err(AbepError::OutOfDomain { message: format!("{name} must be a finite number, got {v}") });
        }
        if !(lo <= v && v <= hi) {
            return Err(AbepError::OutOfDomain {
                message: format!("{name} = {v} outside the {DATASET_ID} domain [{lo}, {hi}]; refusing to extrapolate"),
            });
        }
    }
    Ok(si)
}

/// An interpolated or grid-node atmosphere state (`_state_dict`; field order = the reference dict order).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct OrbitState {
    pub alt_km: f64,
    pub lat_deg: f64,
    pub lst_h: f64,
    pub lon_deg: f64,
    pub doy: f64,
    pub scenario: String,
    pub f107: f64,
    pub f107a: f64,
    pub ap: f64,
    pub rho_kg_m3: f64,
    #[serde(rename = "n_N2_m3")]
    pub n_n2_m3: f64,
    #[serde(rename = "n_O2_m3")]
    pub n_o2_m3: f64,
    #[serde(rename = "n_O_m3")]
    pub n_o_m3: f64,
    #[serde(rename = "n_He_m3")]
    pub n_he_m3: f64,
    #[serde(rename = "n_Ar_m3")]
    pub n_ar_m3: f64,
    #[serde(rename = "n_N_m3")]
    pub n_n_m3: f64,
    pub n_total_m3: f64,
    #[serde(rename = "T_K")]
    pub t_k: f64,
    #[serde(rename = "x_O")]
    pub x_o: f64,
    #[serde(rename = "x_N2")]
    pub x_n2: f64,
    #[serde(rename = "x_O2")]
    pub x_o2: f64,
    #[serde(rename = "x_N")]
    pub x_n: f64,
    #[serde(rename = "x_He")]
    pub x_he: f64,
    #[serde(rename = "x_Ar")]
    pub x_ar: f64,
    pub source: String,
    pub evaluation: String,
    pub interp_max_rel_err_rho: Option<f64>,
}

impl OrbitState {
    /// rho, n_N2, n_O2, n_O, n_He, n_Ar, n_N, n_total, T, x_O, x_N2, x_O2, x_N, x_He, x_Ar
    /// (`abep_data::design_states::THERMO_FIELDS` order).
    pub fn thermo(&self) -> [f64; 15] {
        [
            self.rho_kg_m3,
            self.n_n2_m3,
            self.n_o2_m3,
            self.n_o_m3,
            self.n_he_m3,
            self.n_ar_m3,
            self.n_n_m3,
            self.n_total_m3,
            self.t_k,
            self.x_o,
            self.x_n2,
            self.x_o2,
            self.x_n,
            self.x_he,
            self.x_ar,
        ]
    }
}

/// One sample of `orbit_states` (state + orbit geometry; field order = the reference dict order).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct OrbitSample {
    #[serde(flatten)]
    pub state: OrbitState,
    pub t_s: f64,
    pub u_deg: f64,
    pub ut_h: f64,
    pub inclination_deg: f64,
    pub ltan_h: f64,
    pub orbit_inputs_status: String,
    pub v_orb_m_s: f64,
    pub v_rel_corot_m_s: f64,
    pub flux_corot_kg_m2_s: f64,
    pub wind_included: bool,
    pub wind_open_item: String,
    pub weight: f64,
    pub state_id: String,
    pub geometry: String,
}

/// Caller-supplied orbit (every value required; inclination / LTAN are PARAMETRIC inputs, A9.17 ORBIT). `doy` and
/// `n_samples` are floats validated as integers, as the reference does.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct OrbitRequest<'a> {
    pub alt_km: f64,
    pub inclination_deg: f64,
    pub ltan_h: f64,
    pub scenario: &'a str,
    pub doy: f64,
    pub ut_start_h: f64,
    pub n_samples: f64,
}

pub const ORBIT_INPUTS_STATUS: &str = "PARAMETRIC (caller-supplied; not a requirement input)";
pub const WIND_OPEN_ITEM: &str = "ATM-OI-01";
pub const ORBIT_GEOMETRY: &str =
    "circular, constant geodetic altitude, sun-fixed node at LTAN, co-rotating atmosphere, no winds";

/// The loaded frozen dataset with its log grid.
#[derive(Debug, Clone)]
pub struct OrbitAtmosphere {
    pub pins: FrozenPins,
    pub data: OrbitV1Data,
    /// Per scenario: natural log of `data.grid`.
    pub log_grid: Vec<Vec<f64>>,
}

/// Contract the leading axis of a row-major array with `w` (sum over k in increasing order).
pub fn contract(data: &[f64], w: &[f64]) -> Vec<f64> {
    let rest = data.len() / w.len();
    let mut out = vec![0.0; rest];
    for (k, wk) in w.iter().enumerate() {
        let block = &data[k * rest..(k + 1) * rest];
        for (o, x) in out.iter_mut().zip(block) {
            *o += wk * x;
        }
    }
    out
}

/// Separable contraction of a (doy, alt, lat, lon, lst, cols) array at the coordinates.
pub fn interpolate(grid: &[f64], doy: f64, alt_km: f64, lat_deg: f64, lon_deg: f64, lst_h: f64) -> Vec<f64> {
    let mut r = contract(grid, &axis_weights(Axis::Doy, doy));
    for (axis, x) in [(Axis::Alt, alt_km), (Axis::Lat, lat_deg), (Axis::Lon, lon_deg), (Axis::Lst, lst_h)] {
        r = contract(&r, &axis_weights(axis, x));
    }
    r
}

/// Flat offset of a grid node (doy, alt, lat, lon, lst) in a per-scenario block, in values.
pub fn node_offset(i_doy: usize, i_alt: usize, i_lat: usize, i_lon: usize, i_lst: usize) -> usize {
    ((((i_doy * SHAPE[1] + i_alt) * SHAPE[2] + i_lat) * SHAPE[3] + i_lon) * SHAPE[4] + i_lst) * N_OUT
}

impl OrbitAtmosphere {
    /// `atmosphere_orbit.load()`: the verified frozen dataset (abep_data::orbit_v1::load) and its log grid.
    pub fn load(repo_root: &Path) -> AbepResult<OrbitAtmosphere> {
        let pins = FrozenPins::load(repo_root)?;
        let data = orbit_v1::load(repo_root, &pins)?;
        let log_grid = data.grid.iter().map(|g| g.iter().map(|v| v.ln()).collect()).collect();
        Ok(OrbitAtmosphere { pins, data, log_grid })
    }

    pub fn dataset_sha256(&self) -> &str {
        &self.data.meta.sha256
    }

    #[allow(clippy::too_many_arguments)]
    fn state_dict(
        &self,
        vals: &[f64],
        t: f64,
        si: usize,
        alt_km: f64,
        lat_deg: f64,
        lst_h: f64,
        lon_deg: f64,
        doy: f64,
        interpolated: bool,
    ) -> OrbitState {
        let sc = SCENARIOS[si];
        let n = &vals[1..7];
        let n_tot = n[0] + n[1] + n[2] + n[3] + n[4] + n[5];
        OrbitState {
            alt_km,
            lat_deg,
            lst_h: py_mod(lst_h, 24.0),
            lon_deg: py_mod(lon_deg, 360.0),
            doy,
            scenario: sc.id.to_string(),
            f107: sc.f107,
            f107a: sc.f107a,
            ap: sc.ap,
            rho_kg_m3: vals[0],
            n_n2_m3: n[0],
            n_o2_m3: n[1],
            n_o_m3: n[2],
            n_he_m3: n[3],
            n_ar_m3: n[4],
            n_n_m3: n[5],
            n_total_m3: n_tot,
            t_k: t,
            x_o: n[2] / n_tot,
            x_n2: n[0] / n_tot,
            x_o2: n[1] / n_tot,
            x_n: n[5] / n_tot,
            x_he: n[3] / n_tot,
            x_ar: n[4] / n_tot,
            source: format!("{DATASET_ID} sha256 {}", self.data.meta.sha256),
            evaluation: if interpolated { "interpolated" } else { "grid_node" }.to_string(),
            interp_max_rel_err_rho: if interpolated { self.data.meta.interp_max_rel_err_rho(sc.id) } else { Some(0.0) },
        }
    }

    /// `state(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)`: interpolated state.
    pub fn state(
        &self,
        alt_km: f64,
        lat_deg: f64,
        lst_h: f64,
        lon_deg: f64,
        doy: f64,
        scenario: &str,
    ) -> AbepResult<OrbitState> {
        let si = check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)?;
        let r = interpolate(&self.log_grid[si], doy, alt_km, lat_deg, lon_deg, lst_h);
        let v: Vec<f64> = r.iter().map(|x| x.exp()).collect();
        Ok(self.state_dict(&v[..7], v[7], si, alt_km, lat_deg, lst_h, lon_deg, doy, true))
    }

    /// `node_state(i_doy, i_alt, i_lat, i_lon, i_lst, scenario)`: exact grid-node state.
    pub fn node_state(
        &self,
        i_doy: usize,
        i_alt: usize,
        i_lat: usize,
        i_lon: usize,
        i_lst: usize,
        scenario: &str,
    ) -> AbepResult<OrbitState> {
        let si = scenario_index(scenario).ok_or_else(|| AbepError::OutOfDomain {
            message: format!("scenario {scenario:?} is not in {DATASET_ID}"),
        })?;
        let idx = [i_doy, i_alt, i_lat, i_lon, i_lst];
        if idx.iter().zip(SHAPE).any(|(i, n)| *i >= n) {
            return Err(AbepError::OutOfDomain {
                message: format!("grid node index {idx:?} outside the shape {SHAPE:?}"),
            });
        }
        let o = node_offset(i_doy, i_alt, i_lat, i_lon, i_lst);
        let v = &self.data.grid[si][o..o + N_OUT];
        Ok(self.state_dict(
            &v[..7],
            v[7],
            si,
            ALT_KM[i_alt],
            LAT_DEG[i_lat],
            LST_H[i_lst],
            LON_DEG[i_lon],
            DOY[i_doy],
            false,
        ))
    }

    /// `orbit_states(...)`: one circular revolution at constant geodetic altitude sampled equally in time; relative
    /// speed against a rigidly co-rotating atmosphere (OMEGA_E), no thermospheric wind (open item ATM-OI-01).
    pub fn orbit_states(&self, req: &OrbitRequest) -> AbepResult<Vec<OrbitSample>> {
        let refuse = |m: String| AbepError::OutOfDomain { message: format!("orbit_states: {m}") };
        let n_int = py_int(req.n_samples, "n_samples")?;
        if n_int as f64 != req.n_samples || req.n_samples < 4.0 {
            return Err(refuse("n_samples must be an integer >= 4".into()));
        }
        if !(0.0 <= req.inclination_deg && req.inclination_deg <= 180.0) {
            return Err(refuse("inclination_deg must be in [0, 180]".into()));
        }
        let doy_int = py_int(req.doy, "doy")?;
        if doy_int as f64 != req.doy {
            return Err(refuse("doy must be integral (MSIS day of year)".into()));
        }
        if !(DOMAIN.doy.0 <= req.doy && req.doy <= DOMAIN.doy.1) {
            return Err(refuse(format!("doy = {} outside the {DATASET_ID} domain", req.doy)));
        }
        let n_samples = req.n_samples;
        let a = R_EARTH + req.alt_km * 1e3;
        let v_orb = (MU_EARTH / a).sqrt();
        let t_orb = TWO_PI * (py_pow(a, 3.0) / MU_EARTH).sqrt();
        let inc = radians(req.inclination_deg);
        let mut out = Vec::with_capacity(n_int as usize);
        for k in 0..n_int {
            let kf = k as f64;
            let u = TWO_PI * kf / n_samples;
            let t = t_orb * kf / n_samples;
            let lat = degrees((inc.sin() * u.sin()).asin());
            let dalpha = degrees((inc.cos() * u.sin()).atan2(u.cos()));
            let lst = py_mod(req.ltan_h + dalpha / 15.0, 24.0);
            let ut = py_mod(req.ut_start_h + t / 3600.0, 24.0);
            let doy_k = doy_int + py_int(py_floordiv(req.ut_start_h + t / 3600.0, 24.0), "ut_start_h // 24")?;
            if doy_k as f64 > DOMAIN.doy.1 {
                return Err(refuse(
                    "orbit crosses the end of the dataset year; choose doy/ut_start_h inside it".into(),
                ));
            }
            let lon = py_mod(15.0 * (lst - ut), 360.0);
            let r = [a * u.cos(), a * (inc.cos() * u.sin()), a * (inc.sin() * u.sin())];
            let v = [v_orb * -u.sin(), v_orb * (inc.cos() * u.cos()), v_orb * (inc.sin() * u.cos())];
            // np.cross([0, 0, OMEGA_E], r)
            let cp = [0.0 * r[2] - OMEGA_E * r[1], OMEGA_E * r[0] - 0.0 * r[2], 0.0 * r[1] - 0.0 * r[0]];
            let vr = [v[0] - cp[0], v[1] - cp[1], v[2] - cp[2]];
            let v_rel = (vr[0] * vr[0] + vr[1] * vr[1] + vr[2] * vr[2]).sqrt();
            let s = self.state(req.alt_km, lat, lst, lon, doy_k as f64, req.scenario)?;
            let flux = s.rho_kg_m3 * v_rel;
            out.push(OrbitSample {
                state: s,
                t_s: t,
                u_deg: degrees(u),
                ut_h: ut,
                inclination_deg: req.inclination_deg,
                ltan_h: req.ltan_h,
                orbit_inputs_status: ORBIT_INPUTS_STATUS.to_string(),
                v_orb_m_s: v_orb,
                v_rel_corot_m_s: v_rel,
                flux_corot_kg_m2_s: flux,
                wind_included: false,
                wind_open_item: WIND_OPEN_ITEM.to_string(),
                weight: 1.0 / n_samples,
                state_id: format!("orbit:{}:alt{}:doy{doy_k}:k{k}", req.scenario, py_format_g(req.alt_km)),
                geometry: ORBIT_GEOMETRY.to_string(),
            });
        }
        Ok(out)
    }
}
