//! Frozen orbit-averaged NRLMSIS 2.1 atmosphere (`abep_sim/atmosphere.py`, contract PARITY-C-ABEP_SIM_ATMOSPHERE_PY-V1).
//!
//! Only the frozen-scenario path exists (orbit average over lat -60..60 x 4 LST sectors, ap 15, epoch
//! 2028-03-21T12:00): no live NRLMSIS, no built-in table, no environment switch (A9.29 sec. 6, RM-OQ-02; CLAUDE.md
//! rule 3). Density is interpolated log-linearly in altitude and F10.7, fractions and temperature linearly.

use crate::pyfloat::{np_interp, searchsorted_left};
use abep_data::msis21_v1::{self, Msis21V1};
use abep_data::pins::FrozenPins;
use abep_types::constants::{K_B, MU_EARTH, M_N2, M_O, M_O2, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use std::path::Path;

pub const FROZEN_EPOCH: &str = "2028-03-21T12:00";
pub const AP: f64 = 15.0;
pub const SOLAR_LABELS: [(&str, f64); 3] = [("low", 70.0), ("mean", 150.0), ("high", 230.0)];

/// The `solar` argument: a label (low / mean / high) or a numeric F10.7 (F10.7A taken equal).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum Solar {
    Label(String),
    F107(f64),
}

impl Solar {
    /// F10.7 of the argument; an unknown label is refused (the reference raises KeyError).
    pub fn f107(&self) -> AbepResult<f64> {
        match self {
            Solar::F107(f) => Ok(*f),
            Solar::Label(l) => SOLAR_LABELS.iter().find(|(n, _)| n == l).map(|(_, f)| *f).ok_or_else(|| {
                AbepError::OutOfDomain { message: format!("unknown solar label {l:?} (low, mean, high)") }
            }),
        }
    }
}

/// The verified frozen dataset.
#[derive(Debug, Clone)]
pub struct Msis21Frozen {
    pub data: Msis21V1,
    pub config_manifest_sha256: String,
    pub model_set_sha256: String,
}

impl Msis21Frozen {
    pub fn load(repo_root: &Path) -> AbepResult<Msis21Frozen> {
        let pins = FrozenPins::load(repo_root)?;
        Ok(Msis21Frozen {
            data: msis21_v1::load(repo_root, &pins)?,
            config_manifest_sha256: pins.config_manifest_sha256,
            model_set_sha256: pins.model_set_sha256,
        })
    }
}

/// `atmosphere(...)` result; field order is the reference dict order.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct AtmosphereState {
    pub alt_km: f64,
    pub solar: Solar,
    pub f107: f64,
    pub ap: f64,
    pub rho: f64,
    pub fO: f64,
    pub fN2: f64,
    pub fO2: f64,
    pub m_mean: f64,
    pub n: f64,
    pub T: f64,
    pub V: f64,
    pub flux_kg_m2_s: f64,
    pub p_ambient_Pa: f64,
    pub source: String,
    pub epoch: String,
    pub f107a: f64,
    pub n_O: f64,
}

/// `orbital_velocity(alt_km)` = sqrt(MU_EARTH / (R_EARTH + 1e3 alt_km)). A zero or negative radius is refused (the
/// reference raises ZeroDivisionError / ValueError); a non-finite altitude is refused (DIV-A-04).
pub fn orbital_velocity(alt_km: f64) -> AbepResult<f64> {
    if !alt_km.is_finite() {
        return Err(AbepError::OutOfDomain { message: format!("orbital_velocity: altitude {alt_km} is not finite") });
    }
    let r = R_EARTH + alt_km * 1e3;
    if r <= 0.0 {
        return Err(AbepError::OutOfDomain {
            message: format!("orbital_velocity: orbit radius {r} m is not positive"),
        });
    }
    Ok((MU_EARTH / r).sqrt())
}

/// `_interp_frozen(alt_km, f107)` -> (rho, fO, fN2, fO2, T).
pub fn interp_frozen(fz: &Msis21Frozen, alt_km: f64, f107: f64) -> AbepResult<[f64; 5]> {
    let d = &fz.data;
    let (alts, fs) = (&d.alt_axis, &d.f107_axis);
    let inside = alts[0] <= alt_km && alt_km <= alts[alts.len() - 1] && fs[0] <= f107 && f107 <= fs[fs.len() - 1];
    if !inside {
        return Err(AbepError::OutOfDomain {
            message: format!(
                "frozen atmosphere covers {}-{} km, F10.7 {}-{}; asked {alt_km} km / {f107}",
                alts[0],
                alts[alts.len() - 1],
                fs[0],
                fs[fs.len() - 1]
            ),
        });
    }
    let at_f = |i: usize| -> [f64; 5] {
        let c = &d.columns[i];
        let logs: Vec<f64> = c.rho.iter().map(|r| r.ln()).collect();
        let lr = np_interp(alt_km, &c.alt_km, &logs);
        [
            lr.exp(),
            np_interp(alt_km, &c.alt_km, &c.f_o),
            np_interp(alt_km, &c.alt_km, &c.f_n2),
            np_interp(alt_km, &c.alt_km, &c.f_o2),
            np_interp(alt_km, &c.alt_km, &c.t_k),
        ]
    };
    let i = (searchsorted_left(fs, f107) as i64 - 1).max(0).min(fs.len() as i64 - 2) as usize;
    let (f0, f1) = (fs[i], fs[i + 1]);
    let w = (f107 - f0) / (f1 - f0);
    let (a, b) = (at_f(i), at_f(i + 1));
    let rho = ((1.0 - w) * a[0].ln() + w * b[0].ln()).exp();
    let mut out = [rho, 0.0, 0.0, 0.0, 0.0];
    for k in 1..5 {
        out[k] = (1.0 - w) * a[k] + w * b[k];
    }
    Ok(out)
}

/// `atmosphere(alt_km, solar)` on the frozen scenario.
pub fn atmosphere(fz: &Msis21Frozen, alt_km: f64, solar: Solar) -> AbepResult<AtmosphereState> {
    let f107 = solar.f107()?;
    let [rho, f_o, f_n2, f_o2, t] = interp_frozen(fz, alt_km, f107)?;
    let m_mean = 1.0 / (f_o / M_O + f_n2 / M_N2 + f_o2 / M_O2);
    let n = rho / m_mean;
    let v = orbital_velocity(alt_km)?;
    Ok(AtmosphereState {
        alt_km,
        solar,
        f107,
        ap: AP,
        rho,
        fO: f_o,
        fN2: f_n2,
        fO2: f_o2,
        m_mean,
        n,
        T: t,
        V: v,
        flux_kg_m2_s: rho * v,
        p_ambient_Pa: n * K_B * t,
        source: format!("NRLMSIS 2.1 frozen scenario {}", fz.data.sha256_16),
        epoch: FROZEN_EPOCH.to_string(),
        f107a: f107,
        n_O: rho * f_o / M_O,
    })
}
