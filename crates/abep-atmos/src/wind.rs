//! Frozen HWM14 orbit winds v2 (`abep_sim/atmosphere_orbit_v2.py`: load, wind, state; status
//! DESIGN_ENVELOPE_PARAMETRIC, A9.17 WINDS). Total wind = quiet part interpolated on the v1 grid (v1 weights, linear
//! values) + DWM07 disturbance part interpolated on the disturbance table. HWM14 is not run: a missing or altered
//! frozen table is MODEL_ERROR (A9.29 sec. 6).

use crate::orbit::{check_domain, contract, interpolate, OrbitAtmosphere, OrbitState};
use crate::weights::{axis_weights, lagrange_weights, periodic_cubic_weights, Axis};
use abep_data::hwm14_v2::{self, dist_lat_deg, WindV2Data, DATASET_ID, DATASET_STATUS, HWM14_VERSION};
use abep_data::orbit_v1::SCENARIOS;
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use std::path::Path;

/// `wind(...)` result (field order = the reference dict order).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Wind {
    pub u_mer_quiet_m_s: f64,
    pub u_zon_quiet_m_s: f64,
    pub u_mer_dist_m_s: f64,
    pub u_zon_dist_m_s: f64,
    pub u_mer_m_s: f64,
    pub u_zon_m_s: f64,
    pub ap_hwm: f64,
    pub wind_model: String,
    pub wind_source: String,
    pub wind_interp_max_abs_err_m_s: Option<f64>,
}

/// v2 `state(...)`: the v1 state, the winds and the dataset labels.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StateV2 {
    #[serde(flatten)]
    pub state: OrbitState,
    #[serde(flatten)]
    pub wind: Wind,
    pub dataset_id: String,
    pub dataset_status: String,
}

#[derive(Debug, Clone)]
pub struct WindAtmosphere {
    pub data: WindV2Data,
    dist_lat: Vec<f64>,
}

impl WindAtmosphere {
    /// `atmosphere_orbit_v2.load()` on the loaded, verified v1 dataset.
    pub fn load(repo_root: &Path, orbit: &OrbitAtmosphere) -> AbepResult<WindAtmosphere> {
        Ok(WindAtmosphere { data: hwm14_v2::load(repo_root, &orbit.pins, &orbit.data)?, dist_lat: dist_lat_deg() })
    }

    /// Interpolated HWM14 winds (m/s) at the coordinates; out-of-domain queries are OUT_OF_DOMAIN.
    pub fn wind(
        &self,
        alt_km: f64,
        lat_deg: f64,
        lst_h: f64,
        lon_deg: f64,
        doy: f64,
        scenario: &str,
    ) -> AbepResult<Wind> {
        let si = check_domain(alt_km, lat_deg, lst_h, lon_deg, doy, scenario).map_err(|e| match e {
            AbepError::OutOfDomain { message } => {
                AbepError::OutOfDomain { message: format!("{DATASET_ID}: {message}") }
            }
            other => other,
        })?;
        let q = interpolate(&self.data.quiet[si], doy, alt_km, lat_deg, lon_deg, lst_h);
        let mut d = contract(&self.data.dist[si], &axis_weights(Axis::Doy, doy));
        d = contract(&d, &lagrange_weights(lat_deg, &self.dist_lat));
        d = contract(&d, &periodic_cubic_weights(lon_deg, 360.0, 24));
        d = contract(&d, &periodic_cubic_weights(lst_h, 24.0, 24));
        let sc = SCENARIOS[si];
        Ok(Wind {
            u_mer_quiet_m_s: q[0],
            u_zon_quiet_m_s: q[1],
            u_mer_dist_m_s: d[0],
            u_zon_dist_m_s: d[1],
            u_mer_m_s: q[0] + d[0],
            u_zon_m_s: q[1] + d[1],
            ap_hwm: sc.ap,
            wind_model: format!("HWM14 {HWM14_VERSION}"),
            wind_source: format!(
                "{DATASET_ID} sha256 {} + disturbance sha256 {}",
                self.data.sha256, self.data.disturbance_sha256
            ),
            wind_interp_max_abs_err_m_s: self.data.interp_max_abs_err(sc.id),
        })
    }

    /// v2 `state(...)` = v1 state + winds, labelled DESIGN_ENVELOPE_PARAMETRIC.
    #[allow(clippy::too_many_arguments)]
    pub fn state(
        &self,
        orbit: &OrbitAtmosphere,
        alt_km: f64,
        lat_deg: f64,
        lst_h: f64,
        lon_deg: f64,
        doy: f64,
        scenario: &str,
    ) -> AbepResult<StateV2> {
        let wind = self.wind(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)?;
        let state = orbit.state(alt_km, lat_deg, lst_h, lon_deg, doy, scenario)?;
        Ok(StateV2 { state, wind, dataset_id: DATASET_ID.to_string(), dataset_status: DATASET_STATUS.to_string() })
    }
}
