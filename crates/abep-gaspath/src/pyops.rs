//! Float operations with the semantics of the CPython / numpy operations the reference uses: Python float division
//! and `math` functions raise where IEEE would return inf / NaN; builtin `max` / `min` keep the first argument on a
//! NaN comparison while numpy `maximum` / `minimum` propagate NaN; `repr` and `format(x, 'g')`; numpy pairwise
//! summation, `linspace` / `geomspace`.

use crate::error::{GasPathError, PyClass, PyResult};

/// Python `a / b` for floats: ZeroDivisionError on a zero divisor.
pub fn div(a: f64, b: f64) -> PyResult<f64> {
    if b == 0.0 {
        return Err(GasPathError::new(PyClass::ZeroDivisionError, "float division by zero"));
    }
    Ok(a / b)
}

/// `math.exp`: OverflowError when a finite argument overflows.
pub fn exp(x: f64) -> PyResult<f64> {
    let r = x.exp();
    if r.is_infinite() && x.is_finite() {
        return Err(GasPathError::new(PyClass::OverflowError, "math range error"));
    }
    Ok(r)
}

/// `math.sqrt`: ValueError for a negative argument (NaN passes through).
pub fn sqrt(x: f64) -> PyResult<f64> {
    if x < 0.0 {
        return Err(GasPathError::new(PyClass::ValueError, "math domain error"));
    }
    Ok(x.sqrt())
}

/// `math.log`: ValueError for a non-positive argument (NaN passes through).
pub fn log(x: f64) -> PyResult<f64> {
    if x <= 0.0 {
        return Err(GasPathError::new(PyClass::ValueError, "math domain error"));
    }
    Ok(x.ln())
}

/// Python `x ** y` for floats with a non-negative base (the only case the reference reaches): libm `pow` (the exponent
/// is opaque so the call is never rewritten), ZeroDivisionError for `0.0 ** negative`, OverflowError on overflow.
pub fn pow(x: f64, y: f64) -> PyResult<f64> {
    if x == 0.0 && y < 0.0 {
        return Err(GasPathError::new(PyClass::ZeroDivisionError, "0.0 cannot be raised to a negative power"));
    }
    let r = x.powf(std::hint::black_box(y));
    if r.is_infinite() && x.is_finite() && y.is_finite() {
        return Err(GasPathError::new(PyClass::OverflowError, "(34, 'Numerical result out of range')"));
    }
    Ok(r)
}

/// libm `pow` with an opaque exponent (numpy `power` / `**` on arrays: no exception).
pub fn powf(x: f64, y: f64) -> f64 {
    x.powf(std::hint::black_box(y))
}

/// Builtin `max(a, b)`: `b` replaces `a` only when `b > a`.
pub fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

/// Builtin `min(a, b)`: `b` replaces `a` only when `b < a`.
pub fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

/// Builtin `max(iterable)` (first element kept on ties / NaN comparisons); `None` when empty.
pub fn py_max_iter(xs: impl IntoIterator<Item = f64>) -> Option<f64> {
    let mut it = xs.into_iter();
    let first = it.next()?;
    Some(it.fold(first, py_max))
}

/// Builtin `min(iterable)`; `None` when empty.
pub fn py_min_iter(xs: impl IntoIterator<Item = f64>) -> Option<f64> {
    let mut it = xs.into_iter();
    let first = it.next()?;
    Some(it.fold(first, py_min))
}

/// numpy `maximum(a, b)`: NaN propagates.
pub fn np_maximum(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if b > a {
        b
    } else {
        a
    }
}

/// numpy `minimum(a, b)`: NaN propagates.
pub fn np_minimum(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if b < a {
        b
    } else {
        a
    }
}

/// numpy `ndarray.max()` (NaN propagates).
pub fn np_amax(xs: &[f64]) -> f64 {
    xs.iter().copied().fold(f64::NEG_INFINITY, |a, b| if a.is_nan() || b.is_nan() { f64::NAN } else { a.max(b) })
}

/// numpy `ndarray.min()` (NaN propagates).
pub fn np_amin(xs: &[f64]) -> f64 {
    xs.iter().copied().fold(f64::INFINITY, |a, b| if a.is_nan() || b.is_nan() { f64::NAN } else { a.min(b) })
}

/// numpy `nanmax` (NaN ignored; NaN when every element is NaN).
pub fn np_nanmax(xs: &[f64]) -> f64 {
    let v: Vec<f64> = xs.iter().copied().filter(|x| !x.is_nan()).collect();
    if v.is_empty() {
        f64::NAN
    } else {
        np_amax(&v)
    }
}

/// numpy `nanmin`.
pub fn np_nanmin(xs: &[f64]) -> f64 {
    let v: Vec<f64> = xs.iter().copied().filter(|x| !x.is_nan()).collect();
    if v.is_empty() {
        f64::NAN
    } else {
        np_amin(&v)
    }
}

/// Builtin `sum(iterable)` of floats (CPython 3.11: left to right from 0).
pub fn py_sum(xs: impl IntoIterator<Item = f64>) -> f64 {
    xs.into_iter().fold(0.0, |a, b| a + b)
}

/// numpy `pairwise_sum` of float64 (unrolled by 8, block size 128).
fn pairwise(a: &[f64]) -> f64 {
    let n = a.len();
    if n < 8 {
        let mut res = 0.0;
        for x in a {
            res += *x;
        }
        res
    } else if n <= 128 {
        let mut r = [a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]];
        let mut i = 8;
        while i < n - (n % 8) {
            for k in 0..8 {
                r[k] += a[i + k];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        while i < n {
            res += a[i];
            i += 1;
        }
        res
    } else {
        let mut n2 = n / 2;
        n2 -= n2 % 8;
        pairwise(&a[..n2]) + pairwise(&a[n2..])
    }
}

/// numpy `ndarray.sum()` of a 1-D float64 array: the first element, plus the pairwise sum of the rest.
pub fn np_sum(a: &[f64]) -> f64 {
    match a.len() {
        0 => 0.0,
        _ => a[0] + pairwise(&a[1..]),
    }
}

/// numpy `ndarray.mean()`.
pub fn np_mean(a: &[f64]) -> f64 {
    np_sum(a) / a.len() as f64
}

/// numpy `linspace(start, stop, num)` (endpoint included, float64).
pub fn np_linspace(start: f64, stop: f64, num: usize) -> Vec<f64> {
    if num == 0 {
        return vec![];
    }
    if num == 1 {
        return vec![start];
    }
    let div = (num - 1) as f64;
    let delta = stop - start;
    let step = delta / div;
    let mut y: Vec<f64> = (0..num).map(|i| i as f64).collect();
    if step == 0.0 {
        for v in y.iter_mut() {
            *v = *v / div * delta + start;
        }
    } else {
        for v in y.iter_mut() {
            *v = *v * step + start;
        }
    }
    y[num - 1] = stop;
    y
}

/// numpy `geomspace(start, stop, num)` for positive start / stop.
pub fn np_geomspace(start: f64, stop: f64, num: usize) -> Vec<f64> {
    let lo = start.log10();
    let hi = stop.log10();
    let mut out: Vec<f64> = np_linspace(lo, hi, num).into_iter().map(|e| powf(10.0, e)).collect();
    if num > 0 {
        out[0] = start;
    }
    if num > 1 {
        out[num - 1] = stop;
    }
    out
}

/// `math.isclose(a, b)` with the default rel_tol 1e-9 and abs_tol 0.
pub fn isclose(a: f64, b: f64) -> bool {
    if a == b {
        return true;
    }
    if a.is_infinite() || b.is_infinite() {
        return false;
    }
    let d = (b - a).abs();
    d <= (1e-9 * b.abs()).max(1e-9 * a.abs())
}

/// Shortest round-trip digits and the decimal point position (value = 0.d1d2... x 10^decpt).
fn shortest(x: f64) -> (String, i32) {
    let s = format!("{:e}", x.abs());
    let (mant, exp) = s.split_once('e').expect("exponent form");
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let e: i32 = exp.parse().expect("exponent");
    (digits, e + 1)
}

/// CPython `repr(float)` (shortest round-trip digits; exponent form outside 1e-4 <= |x| < 1e16).
pub fn py_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    if x == 0.0 {
        return format!("{sign}0.0");
    }
    let (d, decpt) = shortest(x);
    let n = d.len() as i32;
    let body = if decpt > 16 || decpt <= -4 {
        let e = decpt - 1;
        let m = if n > 1 { format!("{}.{}", &d[..1], &d[1..]) } else { d.clone() };
        let es = if e < 0 { '-' } else { '+' };
        format!("{m}e{es}{:02}", e.abs())
    } else if decpt <= 0 {
        format!("0.{}{}", "0".repeat((-decpt) as usize), d)
    } else if decpt < n {
        format!("{}.{}", &d[..decpt as usize], &d[decpt as usize..])
    } else {
        format!("{}{}.0", d, "0".repeat((decpt - n) as usize))
    };
    format!("{sign}{body}")
}

/// Python `format(x, 'g')` (precision 6).
pub fn py_format_g(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0".into() } else { "0".into() };
    }
    let sci = format!("{:.5e}", x);
    let (mant, exp) = sci.split_once('e').expect("exponent form");
    let exp: i32 = exp.parse().expect("exponent");
    if (-4..6).contains(&exp) {
        let fixed = format!("{:.*}", (5 - exp) as usize, x);
        strip_zeros(&fixed)
    } else {
        let m = strip_zeros(mant);
        let sign = if exp < 0 { '-' } else { '+' };
        format!("{m}e{sign}{:02}", exp.abs())
    }
}

fn strip_zeros(s: &str) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s.to_string()
    }
}

/// CPython `str(x)` of a Python value as used in f-strings: `repr` for floats.
pub fn fmt_opt(x: Option<f64>) -> String {
    match x {
        None => "None".into(),
        Some(v) => py_repr(v),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_matches_cpython() {
        for (x, s) in [
            (0.05, "0.05"),
            (500.0, "500.0"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1.5e-7, "1.5e-07"),
            (-2.5, "-2.5"),
            (0.1 + 0.2, "0.30000000000000004"),
            (123456.789, "123456.789"),
            (1.2345e20, "1.2345e+20"),
            (-0.0, "-0.0"),
        ] {
            assert_eq!(py_repr(x), s, "{x:e}");
        }
    }

    #[test]
    fn format_g_matches_cpython() {
        for (x, s) in [(0.25, "0.25"), (0.9, "0.9"), (1.0, "1"), (0.5, "0.5"), (20.0, "20"), (1e-5, "1e-05")] {
            assert_eq!(py_format_g(x), s);
        }
    }

    #[test]
    fn python_exceptions() {
        assert_eq!(div(1.0, 0.0).unwrap_err().class, PyClass::ZeroDivisionError);
        assert_eq!(exp(1000.0).unwrap_err().class, PyClass::OverflowError);
        assert_eq!(exp(f64::INFINITY).unwrap(), f64::INFINITY);
        assert_eq!(sqrt(-1.0).unwrap_err().class, PyClass::ValueError);
        assert!(sqrt(f64::NAN).unwrap().is_nan());
        assert_eq!(log(0.0).unwrap_err().class, PyClass::ValueError);
        assert_eq!(py_max(f64::NAN, 1.0).to_bits(), f64::NAN.to_bits());
        assert_eq!(py_max(1.0, f64::NAN), 1.0);
        assert!(np_maximum(1.0, f64::NAN).is_nan());
    }

    #[test]
    fn numpy_sum_and_spaces() {
        let a: Vec<f64> = (0..300).map(|i| 0.1 * i as f64).collect();
        let s = np_sum(&a);
        assert!((s - 4485.0).abs() < 1e-9);
        let g = np_geomspace(1e-6, 60.0, 150);
        assert_eq!(g.len(), 150);
        assert_eq!(g[0], 1e-6);
        assert_eq!(g[149], 60.0);
        let l = np_linspace(0.0, 1.0, 5);
        assert_eq!(l, vec![0.0, 0.25, 0.5, 0.75, 1.0]);
        assert!(isclose(0.38, 0.38 + 1e-12));
        assert!(!isclose(0.38, 0.381));
    }
}
