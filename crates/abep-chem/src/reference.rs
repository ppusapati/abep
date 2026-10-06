//! `abep_sim/rate_tables.py`, reproduced operation by operation (contract PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1).
//!
//! This module keeps the reference's behaviour, including what it does silently: the cross section is held beyond the
//! last tabulated point (tail `hold`), T_e <= 0 gives 0.0, a non-finite T_e gives NaN. Production code uses
//! [`crate::checked`], which refuses those cases. Python exceptions are returned as [`PyException`] with Python's class
//! and message ([`RefError::Python`]). Two documented divergences refuse instead of computing: non-finite table entries
//! (DIV-01) and writer lengths beyond [`WRITER_MAX_ROWS`] (DIV-02) ([`RefError::Refused`], OUT_OF_DOMAIN).

use crate::numpy;
use crate::{GRID_POINTS, ME, QE, QE2, TE_SPAN};
use abep_types::pyjson::{float_repr, py_repr_str, PyException};
use abep_types::AbepError;
use std::f64::consts::PI;
use std::fmt;

/// What a reference call returns instead of a value.
#[derive(Debug, Clone, PartialEq)]
pub enum RefError {
    /// The Python reference raises this exception for the same arguments.
    Python(PyException),
    /// Outside the registered parity domain, where Python propagates garbage or exhausts memory: refused (DIV-01,
    /// DIV-02).
    Refused(AbepError),
}

impl fmt::Display for RefError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RefError::Python(e) => write!(f, "{e}"),
            RefError::Refused(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for RefError {}

impl From<PyException> for RefError {
    fn from(e: PyException) -> Self {
        RefError::Python(e)
    }
}

/// Every Python exception of the reference mirrors an argument outside the function's domain: OUT_OF_DOMAIN.
impl From<RefError> for AbepError {
    fn from(e: RefError) -> Self {
        match e {
            RefError::Python(p) => AbepError::OutOfDomain { message: p.to_string() },
            RefError::Refused(a) => a,
        }
    }
}

pub type RefResult<T> = Result<T, RefError>;

fn py(class: &'static str, message: &str) -> RefError {
    RefError::Python(PyException::new(class, message))
}

/// Treatment of the cross section above the last tabulated energy.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tail {
    /// Keep the last tabulated value up to the integration limit (an extrapolation assumption).
    Hold,
    /// Drop to zero just above the last tabulated energy.
    Zero,
}

impl Tail {
    pub fn as_str(self) -> &'static str {
        match self {
            Tail::Hold => "hold",
            Tail::Zero => "zero",
        }
    }
}

/// The `tail` argument as the Python function receives it: a `str`, or `None`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TailArg {
    Str(String),
    None,
}

impl From<Tail> for TailArg {
    fn from(t: Tail) -> Self {
        TailArg::Str(t.as_str().to_string())
    }
}

impl TailArg {
    /// `if tail not in ("hold", "zero"): raise ValueError(f"tail must be 'hold' or 'zero', got {tail!r}")`.
    pub fn resolve(&self) -> RefResult<Tail> {
        match self {
            TailArg::Str(s) if s == "hold" => Ok(Tail::Hold),
            TailArg::Str(s) if s == "zero" => Ok(Tail::Zero),
            TailArg::Str(s) => Err(py("ValueError", &format!("tail must be 'hold' or 'zero', got {}", py_repr_str(s)))),
            TailArg::None => Err(py("ValueError", "tail must be 'hold' or 'zero', got None")),
        }
    }
}

/// `(QE * te) ** -1.5` with CPython `float_pow` semantics for a positive or non-finite base: base 0 ->
/// `ZeroDivisionError`, an infinite result from a finite base -> `OverflowError` (errno ERANGE); glibc `pow` otherwise.
fn prefactor_pow(te_ev: f64) -> RefResult<f64> {
    let base = QE * te_ev;
    if base == 0.0 {
        return Err(py("ZeroDivisionError", "0.0 cannot be raised to a negative power"));
    }
    let p = base.powf(-1.5);
    if p.is_infinite() && base.is_finite() {
        return Err(py("OverflowError", "(34, 'Numerical result out of range')"));
    }
    Ok(p)
}

/// `math.sqrt(8.0 / (math.pi * ME))`.
fn speed_constant() -> f64 {
    (8.0 / (PI * ME)).sqrt()
}

fn refuse_non_finite(e_ev: &[f64], sigma_m2: &[f64]) -> RefResult<()> {
    if let Some(v) = e_ev.iter().chain(sigma_m2).find(|v| !v.is_finite()) {
        return Err(RefError::Refused(AbepError::OutOfDomain {
            message: format!(
                "cross-section table holds a non-finite value ({}); refused (DIV-01: Python propagates it silently)",
                float_repr(*v)
            ),
        }));
    }
    Ok(())
}

/// `maxwellian_rate(E_eV, sigma_m2, Te_eV, tail)`:
///
/// `k(T_e) = sqrt(8 / (pi m_e)) (e T_e)^(-3/2) e^2 int sigma(E) E exp(-E / T_e) dE` on the grid
/// `unique(E (+ tail points) U linspace(0, Emax, 20000))`, `Emax = max(max(E), 60 T_e)`, sigma linearly interpolated,
/// 0 below the first point, trapezoid rule. Returns m^3/s.
pub fn maxwellian_rate(e_ev: &[f64], sigma_m2: &[f64], te_ev: f64, tail: Tail) -> RefResult<f64> {
    if te_ev <= 0.0 {
        return Ok(0.0);
    }
    if e_ev.is_empty() {
        return Err(py("ValueError", "zero-size array to reduction operation maximum which has no identity"));
    }
    refuse_non_finite(e_ev, sigma_m2)?;
    let e_max_tab = e_ev.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let span = TE_SPAN * te_ev;
    let e_max = if span > e_max_tab { span } else { e_max_tab };
    let (x, sx): (Vec<f64>, Vec<f64>) = if e_max > e_max_tab {
        let mut x = e_ev.to_vec();
        let mut sx = sigma_m2.to_vec();
        match tail {
            Tail::Hold => {
                x.push(e_max);
                let last = *sigma_m2
                    .last()
                    .ok_or_else(|| py("IndexError", "index -1 is out of bounds for axis 0 with size 0"))?;
                sx.push(last);
            }
            Tail::Zero => {
                let last_e = e_ev[e_ev.len() - 1];
                x.extend([last_e.next_up(), e_max]);
                sx.extend([0.0, 0.0]);
            }
        }
        (x, sx)
    } else {
        (e_ev.to_vec(), sigma_m2.to_vec())
    };
    let mut pts = x.clone();
    pts.extend(numpy::linspace_from_zero(e_max, GRID_POINTS));
    let grid = numpy::unique(pts);
    let right = *sx.last().ok_or_else(|| py("IndexError", "index -1 is out of bounds for axis 0 with size 0"))?;
    let sg = numpy::interp(&grid, &x, &sx, 0.0, right)?;
    let integrand: Vec<f64> = grid.iter().zip(&sg).map(|(&g, &s)| s * g * ((-g) / te_ev).exp()).collect();
    let integral = numpy::trapezoid(&integrand, &grid) * QE2;
    let p = prefactor_pow(te_ev)?;
    Ok(speed_constant() * p * integral)
}

/// `tail_sensitivity(E_eV, sigma_m2, eps_values)`: `(eps, (k_hold - k_zero) / k_hold if k_hold > 0 else 0.0)` per mean
/// energy `eps` (T_e = eps / 1.5).
pub fn tail_sensitivity(e_ev: &[f64], sigma_m2: &[f64], eps_values: &[f64]) -> RefResult<Vec<(f64, f64)>> {
    let mut out = Vec::with_capacity(eps_values.len());
    for &eps in eps_values {
        let a = maxwellian_rate(e_ev, sigma_m2, eps / 1.5, Tail::Hold)?;
        let b = maxwellian_rate(e_ev, sigma_m2, eps / 1.5, Tail::Zero)?;
        out.push((eps, if a > 0.0 { (a - b) / a } else { 0.0 }));
    }
    Ok(out)
}

/// CPython `math.sqrt`: a NaN result from a non-NaN argument is `ValueError('math domain error')`.
fn py_sqrt(x: f64) -> RefResult<f64> {
    let r = x.sqrt();
    if r.is_nan() && !x.is_nan() {
        return Err(py("ValueError", "math domain error"));
    }
    Ok(r)
}

/// CPython `math.exp`: an infinite result from a finite argument is `OverflowError('math range error')`.
fn py_exp(x: f64) -> RefResult<f64> {
    let r = x.exp();
    if r.is_infinite() && x.is_finite() {
        return Err(py("OverflowError", "math range error"));
    }
    Ok(r)
}

/// `step_cross_section_rate(sigma0, E_th, Te)`: the closed form for `sigma = sigma0 H(E - E_th)`,
/// `k = sigma0 sqrt(8 e T_e / (pi m_e)) (1 + E_th / T_e) exp(-E_th / T_e)`.
pub fn step_cross_section_rate(sigma0: f64, e_th_ev: f64, te_ev: f64) -> RefResult<f64> {
    let a = sigma0 * py_sqrt(8.0 * QE * te_ev / (PI * ME))?;
    if te_ev == 0.0 {
        return Err(py("ZeroDivisionError", "float division by zero"));
    }
    let b = 1.0 + e_th_ev / te_ev;
    let c = py_exp((-e_th_ev) / te_ev)?;
    Ok(a * b * c)
}

/// The writer refuses tables longer than this (eps_max > 1e6 eV; DIV-02). Python would integrate every row or fail
/// with MemoryError depending on host memory.
pub const WRITER_MAX_ROWS: usize = 1_000_001;

/// What `write_hallthruster_table` writes and returns.
#[derive(Debug, Clone, PartialEq)]
pub struct HallThrusterTable {
    /// `(mean energy eps [eV], k [m^3/s])`, eps = 0, 1, ..., k = 0.0 where T_e = eps / 1.5 is not > 0.
    pub rows: Vec<(f64, f64)>,
    /// The bytes of `path`.
    pub text: String,
    /// The bytes of `path + ".source"`; `None` when `source` is empty (no sidecar is written).
    pub source_text: Option<String>,
}

/// `write_hallthruster_table(path, E_eV, sigma_m2, threshold_eV, eps_max, source, tail, header_label)` without the
/// file system: rows for `eps` in `np.arange(0.0, eps_max + 1.0, 1.0)`, then the text written to `path` and to
/// `path + ".source"`. The tail argument is resolved only when a row with T_e > 0 is integrated, as in Python.
pub fn hallthruster_table(
    e_ev: &[f64],
    sigma_m2: &[f64],
    threshold_ev: f64,
    eps_max: f64,
    tail: &TailArg,
    header_label: &str,
    source: &str,
) -> RefResult<HallThrusterTable> {
    let n = numpy::arange_len(0.0, eps_max + 1.0, 1.0)?;
    if n > WRITER_MAX_ROWS {
        return Err(RefError::Refused(AbepError::OutOfDomain {
            message: format!(
                "eps_max {} gives {n} rows, beyond the registered writer domain ({WRITER_MAX_ROWS} rows, eps_max <= 1e6 eV; DIV-02)",
                float_repr(eps_max)
            ),
        }));
    }
    let mut rows = Vec::with_capacity(n);
    for eps in numpy::arange_values(0.0, 1.0, n) {
        let te = eps / 1.5;
        let k = if te > 0.0 { maxwellian_rate(e_ev, sigma_m2, te, tail.resolve()?)? } else { 0.0 };
        rows.push((eps, k));
    }
    let text = render_hallthruster_table(threshold_ev, header_label, &rows);
    let source_text = if source.is_empty() { None } else { Some(format!("{source}\n")) };
    Ok(HallThrusterTable { rows, text, source_text })
}

/// The table text of `write_hallthruster_table`: `f"{header_label} (eV): {threshold_eV}\n"`, the column header, then
/// `f"{eps:.1f}\t{k:.6e}\n"` per row (HallThruster.jl reads the number after the colon only).
pub fn render_hallthruster_table(threshold_ev: f64, header_label: &str, rows: &[(f64, f64)]) -> String {
    let mut s = format!("{header_label} (eV): {}\n", float_repr(threshold_ev));
    s.push_str("Energy (eV)\tRate coefficient (m^3/s)\n");
    for &(eps, k) in rows {
        s.push_str(&format_fixed(eps, 1));
        s.push('\t');
        s.push_str(&format_exp(k, 6));
        s.push('\n');
    }
    s
}

/// Python `format(x, f".{prec}e")`: correctly rounded (ties to even), sign and at least two exponent digits.
pub fn format_exp(x: f64, prec: usize) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let s = format!("{x:.prec$e}");
    let (mantissa, exp) = s.split_once('e').expect("LowerExp output has an exponent");
    let e: i32 = exp.parse().expect("LowerExp exponent is an integer");
    format!("{mantissa}e{}{:02}", if e < 0 { '-' } else { '+' }, e.unsigned_abs())
}

/// Python `format(x, f".{prec}f")` for finite `x` (correctly rounded, ties to even).
pub fn format_fixed(x: f64, prec: usize) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    format!("{x:.prec$}")
}

#[cfg(test)]
mod tests {
    use super::*;

    const STEP_E: [f64; 4] = [0.0, 14.99, 15.0, 1000.0];
    const STEP_S: [f64; 4] = [0.0, 0.0, 1e-20, 1e-20];

    #[test]
    fn integrator_matches_the_step_closed_form() {
        // tests/test_sim.py test_v17_maxwellian_integrator_matches_closed_form (INV-03 criterion)
        for te in [3.0, 10.0, 30.0] {
            let k = maxwellian_rate(&STEP_E, &STEP_S, te, Tail::Hold).unwrap();
            let c = step_cross_section_rate(1e-20, 15.0, te).unwrap();
            assert!((k / c - 1.0).abs() < 0.01, "T_e {te}: {k} vs {c}");
        }
    }

    #[test]
    fn reference_silent_cases_are_kept() {
        assert_eq!(maxwellian_rate(&STEP_E, &STEP_S, 0.0, Tail::Hold).unwrap(), 0.0);
        assert_eq!(maxwellian_rate(&STEP_E, &STEP_S, -1.0, Tail::Zero).unwrap(), 0.0);
        assert_eq!(maxwellian_rate(&[], &[], 0.0, Tail::Hold).unwrap(), 0.0);
        assert!(maxwellian_rate(&STEP_E, &STEP_S, f64::NAN, Tail::Hold).unwrap().is_nan());
        assert!(maxwellian_rate(&STEP_E, &STEP_S, f64::INFINITY, Tail::Hold).unwrap().is_nan());
        assert_eq!(maxwellian_rate(&STEP_E, &[0.0, 0.0, 0.0, 0.0], 5.0, Tail::Hold).unwrap(), 0.0);
    }

    #[test]
    fn python_exceptions_are_mirrored() {
        let cls = |r: RefResult<f64>| match r {
            Err(RefError::Python(p)) => (p.class, p.message),
            other => panic!("expected a Python exception, got {other:?}"),
        };
        assert_eq!(cls(maxwellian_rate(&[], &[], 3.0, Tail::Hold)).0, "ValueError");
        assert_eq!(cls(maxwellian_rate(&[1.0], &[], 3.0, Tail::Hold)).0, "IndexError");
        assert_eq!(cls(maxwellian_rate(&[1.0], &[], 3.0, Tail::Zero)).1, "fp and xp are not of the same length.");
        assert_eq!(cls(maxwellian_rate(&STEP_E, &STEP_S, 1e-310, Tail::Hold)).0, "ZeroDivisionError");
        assert_eq!(cls(maxwellian_rate(&STEP_E, &STEP_S, 1e-200, Tail::Hold)).0, "OverflowError");
        assert_eq!(cls(step_cross_section_rate(1e-20, 15.0, 0.0)).0, "ZeroDivisionError");
        assert_eq!(cls(step_cross_section_rate(1e-20, 15.0, -1.0)).1, "math domain error");
        assert_eq!(cls(step_cross_section_rate(1e-20, -50.0, 0.05)).1, "math range error");
        let t = TailArg::Str("Hold".into()).resolve().unwrap_err();
        assert_eq!(t.to_string(), "ValueError: tail must be 'hold' or 'zero', got 'Hold'");
        assert_eq!(
            TailArg::None.resolve().unwrap_err().to_string(),
            "ValueError: tail must be 'hold' or 'zero', got None"
        );
    }

    #[test]
    fn non_finite_tables_are_refused() {
        let r = maxwellian_rate(&[0.0, f64::NAN, 15.0], &[0.0, 0.0, 1e-20], 3.0, Tail::Hold);
        assert!(matches!(r, Err(RefError::Refused(AbepError::OutOfDomain { .. }))));
    }

    #[test]
    fn writer_rows_text_and_tail_resolution() {
        let t = hallthruster_table(&STEP_E, &STEP_S, 15.0, 3.0, &Tail::Hold.into(), "Ionization energy", "").unwrap();
        assert_eq!(t.rows.len(), 4);
        assert_eq!(t.rows[0], (0.0, 0.0));
        assert!(t
            .text
            .starts_with("Ionization energy (eV): 15.0\nEnergy (eV)\tRate coefficient (m^3/s)\n0.0\t0.000000e+00\n"));
        assert_eq!(t.source_text, None);
        let bogus = TailArg::Str("bogus".into());
        let ok = hallthruster_table(&STEP_E, &STEP_S, 15.0, 0.0, &bogus, "L", "s").unwrap();
        assert_eq!((ok.rows.len(), ok.source_text.as_deref()), (1, Some("s\n")));
        assert!(matches!(hallthruster_table(&STEP_E, &STEP_S, 15.0, 2.0, &bogus, "L", ""), Err(RefError::Python(_))));
        assert!(matches!(
            hallthruster_table(&STEP_E, &STEP_S, 15.0, 1e15, &Tail::Hold.into(), "L", ""),
            Err(RefError::Refused(_))
        ));
    }

    #[test]
    fn python_number_formatting() {
        assert_eq!(format_exp(0.0, 6), "0.000000e+00");
        assert_eq!(format_exp(1.5e-5, 6), "1.500000e-05");
        assert_eq!(format_exp(2.5e100, 6), "2.500000e+100");
        assert_eq!(format_exp(-3.25e-15, 6), "-3.250000e-15");
        // exact ties round to even, as Python's correctly rounded formatting
        assert_eq!(format_exp(1234568.5, 6), "1.234568e+06");
        assert_eq!(format_exp(1234567.5, 6), "1.234568e+06");
        assert_eq!(format_fixed(300.0, 1), "300.0");
        assert_eq!(format_fixed(0.25, 1), "0.2");
    }
}
