//! State propagation of `abep_sim/mission_env.py` (SC-WP-09 existing-physics element; contract
//! PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1): beta angle, eclipse fraction, worst eclipse season, array sizing
//! and the secular J2 / energy-balance propagation with injected drag and thrust callables.
//!
//! The operation order, the libm calls and the Python exception classes of the reference are reproduced: a refusal is
//! `AbepError::OutOfDomain` whose message starts with the Python class (`ValueError: ...`). A NaN input (or a NaN
//! returned by a callable), which the reference propagates or clips silently, is refused with the key `DIV-P-01`
//! (fail closed). The `Spacecraft` defaults (array efficiency, degradation, housekeeping, mass, orbit) are CODE_DEFAULT
//! values of the reference, never evidence; inc_deg / ltan_h are CODE_DEFAULT / PARAMETRIC (A9.17 ORBIT).
//!
//! Not ported: `spacecraft_drag` (unsourced defaults, class-H callers only), `pointing_factors` (sole caller
//! `spacecraft_drag`; AUDITED_NOT_PORTED), `plume_interaction` and `ARRAY_AREAL_KG_M2` (class-H callers).

use abep_atmos::mission_env_kernel::{Spacecraft, J2};
use abep_atmos::pyfloat::{degrees, py_mod, py_pow, radians};
use abep_types::constants::{MU_EARTH, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;

/// Solar constant of the reference, W m-2 (literature value carried by the reference; verify against the TSI record).
pub const SOLAR_CONST: f64 = 1361.0;
const PI: f64 = std::f64::consts::PI;

fn py_err(class: &str, msg: impl std::fmt::Display) -> AbepError {
    AbepError::OutOfDomain { message: format!("{class}: {msg}") }
}

fn domain() -> AbepError {
    py_err("ValueError", "math domain error")
}

fn nan_refused(what: &str) -> AbepError {
    AbepError::OutOfDomain { message: format!("DIV-P-01: NaN {what} refused (the reference would propagate it)") }
}

fn no_nan(values: &[(&str, f64)]) -> AbepResult<()> {
    match values.iter().find(|(_, v)| v.is_nan()) {
        Some((name, _)) => Err(nan_refused(name)),
        None => Ok(()),
    }
}

fn sc_no_nan(sc: &Spacecraft) -> AbepResult<()> {
    no_nan(&[
        ("Spacecraft.mass_kg", sc.mass_kg),
        ("Spacecraft.array_area_m2", sc.array_area_m2),
        ("Spacecraft.array_eff", sc.array_eff),
        ("Spacecraft.array_deg_per_yr", sc.array_deg_per_yr),
        ("Spacecraft.eps_eff", sc.eps_eff),
        ("Spacecraft.bus_housekeeping_W", sc.bus_housekeeping_W),
        ("Spacecraft.inc_deg", sc.inc_deg),
        ("Spacecraft.ltan_h", sc.ltan_h),
    ])
}

/// `math.sin` (ValueError for an infinite argument).
fn sin(x: f64) -> AbepResult<f64> {
    if x.is_infinite() {
        return Err(domain());
    }
    Ok(x.sin())
}

/// `math.cos` (ValueError for an infinite argument).
fn cos(x: f64) -> AbepResult<f64> {
    if x.is_infinite() {
        return Err(domain());
    }
    Ok(x.cos())
}

/// `math.asin` (ValueError outside [-1, 1]).
fn asin(x: f64) -> AbepResult<f64> {
    if x.abs() > 1.0 {
        return Err(domain());
    }
    Ok(x.asin())
}

/// `math.acos` (ValueError outside [-1, 1]).
fn acos(x: f64) -> AbepResult<f64> {
    if x.abs() > 1.0 {
        return Err(domain());
    }
    Ok(x.acos())
}

/// `math.sqrt` (ValueError for a negative argument; -0.0 is allowed).
fn sqrt(x: f64) -> AbepResult<f64> {
    if x < 0.0 {
        return Err(domain());
    }
    Ok(x.sqrt())
}

/// CPython float division (ZeroDivisionError for a zero divisor).
fn div(a: f64, b: f64) -> AbepResult<f64> {
    if b == 0.0 {
        return Err(py_err("ZeroDivisionError", "float division by zero"));
    }
    Ok(a / b)
}

/// CPython `x ** y` for floats (libm pow): 0 ** negative is ZeroDivisionError, a negative base with a non-integer
/// exponent is ValueError, an infinite result from finite operands is OverflowError.
fn pow(x: f64, y: f64) -> AbepResult<f64> {
    if x == 0.0 && y < 0.0 {
        return Err(py_err("ZeroDivisionError", "0.0 cannot be raised to a negative power"));
    }
    if x < 0.0 && x.is_finite() && y.is_finite() && y.floor() != y {
        return Err(py_err("ValueError", "negative number cannot be raised to a fractional power"));
    }
    let r = py_pow(x, y);
    if r.is_infinite() && x.is_finite() && y.is_finite() {
        return Err(py_err("OverflowError", "(34, 'Numerical result out of range')"));
    }
    Ok(r)
}

/// CPython `int(x)` of a float.
fn py_int(x: f64) -> AbepResult<i64> {
    if x.is_nan() {
        return Err(py_err("ValueError", "cannot convert float NaN to integer"));
    }
    if x.is_infinite() {
        return Err(py_err("OverflowError", "cannot convert float infinity to integer"));
    }
    let t = x.trunc();
    if t.abs() >= 9.2e18 {
        return Err(py_err("OverflowError", "integer range exceeded"));
    }
    Ok(t as i64)
}

/// Python `max(a, b)`: `a` unless `b > a`.
fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

/// Python `min(a, b)`: `a` unless `b < a`.
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

/// `beta_angle(inc, raan, sun_lon, sun_dec)`: Sun elevation above the orbit plane, degrees.
pub fn beta_angle(inc_deg: f64, raan_deg: f64, sun_lon_deg: f64, sun_dec_deg: f64) -> AbepResult<f64> {
    no_nan(&[
        ("inc_deg", inc_deg),
        ("raan_deg", raan_deg),
        ("sun_lon_deg", sun_lon_deg),
        ("sun_dec_deg", sun_dec_deg),
    ])?;
    beta_angle_unchecked(inc_deg, raan_deg, sun_lon_deg, sun_dec_deg)
}

fn beta_angle_unchecked(inc_deg: f64, raan_deg: f64, sun_lon_deg: f64, sun_dec_deg: f64) -> AbepResult<f64> {
    let (i, o, ls, d) = (radians(inc_deg), radians(raan_deg), radians(sun_lon_deg), radians(sun_dec_deg));
    let x = cos(d)? * sin(i)? * sin(o - ls)? + sin(d)? * cos(i)?;
    Ok(degrees(asin(x)?))
}

/// `eclipse_fraction(alt_km, beta_deg)`: fraction of a circular orbit in the cylindrical Earth shadow.
pub fn eclipse_fraction(alt_km: f64, beta_deg: f64) -> AbepResult<f64> {
    no_nan(&[("alt_km", alt_km), ("beta_deg", beta_deg)])?;
    eclipse_fraction_unchecked(alt_km, beta_deg)
}

fn eclipse_fraction_unchecked(alt_km: f64, beta_deg: f64) -> AbepResult<f64> {
    let a = R_EARTH + alt_km * 1e3;
    let b = radians(beta_deg.abs());
    let arg = if cos(b)? > 0.0 {
        let s = sqrt(py_max(pow(a, 2.0)? - pow(R_EARTH, 2.0)?, 0.0))?;
        div(s, a * cos(b)?)?
    } else {
        0.0
    };
    if arg >= 1.0 || cos(b)? == 0.0 {
        return Ok(0.0);
    }
    Ok(acos(arg)? / PI)
}

/// `worst_eclipse_fraction(sc, alt_km)`: maximum eclipse fraction over a year (every second day), with the RAAN
/// tracking the spacecraft LTAN (sun-synchronous).
pub fn worst_eclipse_fraction(sc: &Spacecraft, alt_km: f64) -> AbepResult<f64> {
    sc_no_nan(sc)?;
    no_nan(&[("alt_km", alt_km)])?;
    worst_eclipse_fraction_unchecked(sc, alt_km)
}

fn worst_eclipse_fraction_unchecked(sc: &Spacecraft, alt_km: f64) -> AbepResult<f64> {
    let mut fmax = 0.0;
    for day in (0..366).step_by(2) {
        let sun_lon = py_mod(day as f64 / 365.25 * 360.0, 360.0);
        let dec = 23.44 * sin(radians(sun_lon))?;
        let raan = py_mod(sun_lon + (sc.ltan_h - 12.0) * 15.0, 360.0);
        fmax = py_max(fmax, eclipse_fraction_unchecked(alt_km, beta_angle_unchecked(sc.inc_deg, raan, sun_lon, dec)?)?);
    }
    Ok(fmax)
}

/// `array_area_for(P_prop_W, sc, alt_km, years, rho_max_over_design, P_cap_W)`: array area for the worst eclipse
/// season, end of life and solar-maximum drag. `p_cap_w` is explicit (the reference's `None` resolves to the operating
/// scenario's P_bus throttling cap, `abep_config::OperatingInputs::p_bus_max_w`).
pub fn array_area_for(
    p_prop_w: f64,
    sc: &Spacecraft,
    alt_km: f64,
    years: f64,
    rho_max_over_design: f64,
    p_cap_w: f64,
) -> AbepResult<f64> {
    sc_no_nan(sc)?;
    no_nan(&[
        ("P_prop_W", p_prop_w),
        ("alt_km", alt_km),
        ("years", years),
        ("rho_max_over_design", rho_max_over_design),
        ("P_cap_W", p_cap_w),
    ])?;
    let f_ecl = worst_eclipse_fraction_unchecked(sc, alt_km)?;
    let p = py_min(p_prop_w * rho_max_over_design, p_cap_w);
    let eol = 1.0 - sc.array_deg_per_yr * years;
    div(p + sc.bus_housekeeping_W, SOLAR_CONST * sc.array_eff * eol * (1.0 - f_ecl) * sc.eps_eff)
}

/// What a drag callable returns: total drag and the atmosphere density at the step (`(D, atm)` of the reference).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DragSample {
    pub d_n: f64,
    pub rho: f64,
}

/// What a thrust callable sees: the density and the available array power `atm["_P_avail"]` of the step.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ThrustContext {
    pub rho: f64,
    pub p_avail_w: f64,
}

/// What a thrust callable returns: thrust and propulsion bus power (`(T, P_bus)`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ThrustSample {
    pub t_n: f64,
    pub p_bus_w: f64,
}

/// One propagation step (the reference DataFrame row, same columns and order).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct PropagationRow {
    pub t_h: f64,
    pub alt_km: f64,
    pub raan_deg: f64,
    pub beta_deg: f64,
    pub eclipse_frac: f64,
    pub D_mN: f64,
    pub T_mN: f64,
    pub P_bus_W: f64,
    pub P_need_W: f64,
    pub P_avail_W: f64,
    pub power_margin_W: f64,
    pub rho: f64,
}

/// The reference DataFrame columns, in order.
pub const PROPAGATION_COLUMNS: [&str; 12] = [
    "t_h",
    "alt_km",
    "raan_deg",
    "beta_deg",
    "eclipse_frac",
    "D_mN",
    "T_mN",
    "P_bus_W",
    "P_need_W",
    "P_avail_W",
    "power_margin_W",
    "rho",
];

/// The reference summary keys, in order.
pub const PROPAGATION_SUMMARY_KEYS: [&str; 6] =
    ["reentered", "min_alt_km", "mean_eclipse", "min_power_margin_W", "hours_power_short", "raan_drift_deg_per_day"];

impl PropagationRow {
    /// The row values in [`PROPAGATION_COLUMNS`] order.
    pub fn values(&self) -> [f64; 12] {
        [
            self.t_h,
            self.alt_km,
            self.raan_deg,
            self.beta_deg,
            self.eclipse_frac,
            self.D_mN,
            self.T_mN,
            self.P_bus_W,
            self.P_need_W,
            self.P_avail_W,
            self.power_margin_W,
            self.rho,
        ]
    }
}

/// The propagation result (rows plus the reference summary).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct Propagation {
    pub rows: Vec<PropagationRow>,
    pub reentered: bool,
    pub min_alt_km: f64,
    pub mean_eclipse: f64,
    pub min_power_margin_W: f64,
    pub hours_power_short: f64,
    pub raan_drift_deg_per_day: f64,
}

/// numpy median of a non-empty slice: the middle element, or (a + b) / 2 of the two middle elements.
fn median(v: &[f64]) -> f64 {
    let mut s = v.to_vec();
    s.sort_by(f64::total_cmp);
    let n = s.len();
    if n % 2 == 1 {
        s[n / 2]
    } else {
        (s[n / 2 - 1] + s[n / 2]) / 2.0
    }
}

/// `propagate(sc, alt0_km, hours, dt_h, drag_fn, thrust_fn, raan0_deg=None, epoch_day=80.0)`: secular J2 RAAN drift,
/// altitude from the energy balance with the full drag and thrust, beta / eclipse and array power; stops below 150 km.
#[allow(clippy::too_many_arguments)]
pub fn propagate<D, T>(
    sc: &Spacecraft,
    alt0_km: f64,
    hours: f64,
    dt_h: f64,
    mut drag_fn: D,
    mut thrust_fn: T,
    raan0_deg: Option<f64>,
    epoch_day: f64,
) -> AbepResult<Propagation>
where
    D: FnMut(f64, f64) -> AbepResult<DragSample>,
    T: FnMut(f64, f64, &ThrustContext) -> AbepResult<ThrustSample>,
{
    sc_no_nan(sc)?;
    no_nan(&[("alt0_km", alt0_km), ("epoch_day", epoch_day), ("raan0_deg", raan0_deg.unwrap_or(0.0))])?;
    let n = py_int(div(hours, dt_h)?)?;
    let mut alt = alt0_km;
    let sun_lon0 = py_mod(epoch_day / 365.25 * 360.0, 360.0);
    let mut raan = match raan0_deg {
        None => py_mod(sun_lon0 + (sc.ltan_h - 12.0) * 15.0, 360.0),
        Some(r) => r,
    };
    let mut rows = Vec::new();
    for k in 0..n.max(0) {
        let t_h = k as f64 * dt_h;
        let a = R_EARTH + alt * 1e3;
        let nmo = sqrt(div(MU_EARTH, pow(a, 3.0)?)?)?;
        let raan_dot = -1.5 * nmo * J2 * pow(div(R_EARTH, a)?, 2.0)? * cos(radians(sc.inc_deg))?;
        raan += degrees(raan_dot * dt_h * 3600.0);
        let day = epoch_day + t_h / 24.0;
        let sun_lon = py_mod(day / 365.25 * 360.0, 360.0);
        let sun_dec = 23.44 * sin(radians(sun_lon))?;
        let beta = beta_angle_unchecked(sc.inc_deg, raan, sun_lon, sun_dec)?;
        let f_ecl = eclipse_fraction_unchecked(alt, beta)?;
        let drag = drag_fn(alt, t_h)?;
        no_nan(&[("drag_fn D", drag.d_n), ("drag_fn rho", drag.rho)])?;
        let yrs0 = t_h / 8766.0;
        let p_avail_atm = sc.array_area_m2
            * SOLAR_CONST
            * sc.array_eff
            * (1.0 - sc.array_deg_per_yr * yrs0)
            * (1.0 - f_ecl)
            * sc.eps_eff;
        let thrust = thrust_fn(alt, t_h, &ThrustContext { rho: drag.rho, p_avail_w: p_avail_atm })?;
        no_nan(&[("thrust_fn T", thrust.t_n), ("thrust_fn P_bus", thrust.p_bus_w)])?;
        let dadt = div(2.0 * pow(a, 1.5)? * (thrust.t_n - drag.d_n), sc.mass_kg * MU_EARTH.sqrt())?;
        alt += dadt * dt_h * 3600.0 / 1e3;
        let yrs = t_h / 8766.0;
        let p_arr = sc.array_area_m2
            * SOLAR_CONST
            * sc.array_eff
            * (1.0 - sc.array_deg_per_yr * yrs)
            * cos(radians(py_max(0.0, 90.0 - beta.abs()) * 0.0))?;
        let p_avail = p_arr * (1.0 - f_ecl) * sc.eps_eff;
        let p_need = thrust.p_bus_w + sc.bus_housekeeping_W;
        rows.push(PropagationRow {
            t_h,
            alt_km: alt,
            raan_deg: py_mod(raan, 360.0),
            beta_deg: beta,
            eclipse_frac: f_ecl,
            D_mN: drag.d_n * 1e3,
            T_mN: thrust.t_n * 1e3,
            P_bus_W: thrust.p_bus_w,
            P_need_W: p_need,
            P_avail_W: p_avail,
            power_margin_W: p_avail - p_need,
            rho: drag.rho,
        });
        if alt < 150.0 {
            break;
        }
    }
    let last = rows.last().ok_or_else(|| py_err("AttributeError", "'DataFrame' object has no attribute 'alt_km'"))?;
    let col = |f: fn(&PropagationRow) -> f64| rows.iter().map(f).collect::<Vec<f64>>();
    let min = |v: Vec<f64>| v.into_iter().reduce(|m, x| if x < m { x } else { m }).unwrap_or(f64::NAN);
    let ecl = col(|r| r.eclipse_frac);
    let mean_eclipse = abep_chem::numpy::sum(&ecl) / ecl.len() as f64;
    let short = rows.iter().filter(|r| r.power_margin_W < 0.0).count();
    let raan_drift = if rows.len() > 2 {
        let d: Vec<f64> = rows.windows(2).map(|w| (w[1].raan_deg - w[0].raan_deg).abs()).collect();
        median(&d) / (dt_h / 24.0)
    } else {
        0.0
    };
    Ok(Propagation {
        reentered: last.alt_km < 150.0,
        min_alt_km: min(col(|r| r.alt_km)),
        mean_eclipse,
        min_power_margin_W: min(col(|r| r.power_margin_W)),
        hours_power_short: short as f64 * dt_h,
        raan_drift_deg_per_day: raan_drift,
        rows,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::EvalStatus;

    #[test]
    fn eclipse_ordering_of_the_reference_test() {
        let e = |b: f64| eclipse_fraction(200.0, b).unwrap();
        assert!(e(0.0) > e(60.0) && e(60.0) > e(80.0) && e(80.0) == 0.0);
    }

    #[test]
    fn worst_eclipse_and_array_area_of_the_reference_test() {
        let sc = Spacecraft::default();
        let f = worst_eclipse_fraction(&sc, 200.0).unwrap();
        assert!(0.25 < f && f < 0.40, "{f}");
        let a = |p: f64| array_area_for(p, &sc, 200.0, 3.0, 1.39, 1500.0).unwrap();
        assert!(a(1000.0) > a(700.0));
        assert_eq!(a(5000.0), a(1500.0));
    }

    #[test]
    fn domain_errors_carry_the_python_class() {
        let e = eclipse_fraction(-6371.0, 0.0).unwrap_err();
        assert_eq!(e.status(), EvalStatus::OutOfDomain);
        assert!(e.to_string().contains("ZeroDivisionError"), "{e}");
        assert!(beta_angle(f64::INFINITY, 0.0, 0.0, 0.0).unwrap_err().to_string().contains("ValueError"));
        assert!(eclipse_fraction(200.0, f64::NAN).unwrap_err().to_string().contains("DIV-P-01"));
    }

    #[test]
    fn tracking_thrust_keeps_the_altitude_exactly() {
        let sc = Spacecraft::default();
        let dens = |alt: f64| 2.5e-10 * (-(alt - 200.0) / 40.0).exp();
        let dragv = |rho: f64, alt: f64| {
            let v = (MU_EARTH / (R_EARTH + alt * 1e3)).sqrt();
            0.5 * rho * py_pow(v, 2.0) * 0.3
        };
        let p = propagate(
            &sc,
            200.0,
            48.0,
            1.0,
            |alt, _| Ok(DragSample { d_n: dragv(dens(alt), alt), rho: dens(alt) }),
            |alt, _, c| Ok(ThrustSample { t_n: dragv(c.rho, alt), p_bus_w: 900.0 }),
            None,
            80.0,
        )
        .unwrap();
        assert_eq!(p.rows.len(), 48);
        assert!(p.rows.iter().all(|r| r.alt_km == 200.0));
        assert!(!p.reentered);
    }

    #[test]
    fn zero_rows_is_the_reference_attribute_error() {
        let e = propagate(
            &Spacecraft::default(),
            200.0,
            0.5,
            1.0,
            |_, _| Ok(DragSample { d_n: 0.0, rho: 1e-10 }),
            |_, _, _| Ok(ThrustSample { t_n: 0.0, p_bus_w: 0.0 }),
            None,
            80.0,
        )
        .unwrap_err();
        assert!(e.to_string().starts_with("OUT_OF_DOMAIN: AttributeError"), "{e}");
    }
}
