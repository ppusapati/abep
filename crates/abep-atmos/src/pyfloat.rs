//! Float operations with the exact semantics of the CPython / numpy operations the reference uses (parity contracts
//! of ES-2): remainder and floor division of `float`, `int(float)`, `math.degrees` / `math.radians`, `np.interp`,
//! `np.searchsorted` and the `'g'` / `'+.4f'` formats used in state ids.

use abep_types::{AbepError, AbepResult};
use std::f64::consts::PI;

/// CPython `math.pi * 2.0` (exact doubling).
pub const TWO_PI: f64 = 2.0 * PI;
const RAD_TO_DEG: f64 = 180.0 / PI;
const DEG_TO_RAD: f64 = PI / 180.0;

/// `math.degrees(x)` = x * (180 / pi).
pub fn degrees(x: f64) -> f64 {
    x * RAD_TO_DEG
}

/// `math.radians(x)` = x * (pi / 180).
pub fn radians(x: f64) -> f64 {
    x * DEG_TO_RAD
}

/// `x ** n` for a float base and an integer exponent: CPython calls libm `pow` (the exponent is opaque so the call is
/// never rewritten into multiplications).
pub fn py_pow(x: f64, n: f64) -> f64 {
    x.powf(std::hint::black_box(n))
}

/// CPython `float.__mod__` (`x % y`): `fmod`, then the result takes the sign of `y`; a zero result is `copysign(0, y)`.
pub fn py_mod(x: f64, y: f64) -> f64 {
    let m = x % y;
    if m != 0.0 {
        if (y < 0.0) != (m < 0.0) {
            m + y
        } else {
            m
        }
    } else {
        0.0_f64.copysign(y)
    }
}

/// CPython `float.__floordiv__` (`x // y`, `y != 0`).
pub fn py_floordiv(x: f64, y: f64) -> f64 {
    let m = x % y;
    let mut div = (x - m) / y;
    if m != 0.0 && ((y < 0.0) != (m < 0.0)) {
        div -= 1.0;
    }
    if div != 0.0 {
        let mut fl = div.floor();
        if div - fl > 0.5 {
            fl += 1.0;
        }
        fl
    } else {
        0.0_f64.copysign(x / y)
    }
}

/// `int(x)` for a float: NaN -> ValueError, +-inf -> OverflowError (both refused as OUT_OF_DOMAIN by the callers).
pub fn py_int(x: f64, what: &str) -> AbepResult<i64> {
    if !x.is_finite() {
        return Err(AbepError::OutOfDomain { message: format!("{what} = {x} cannot be converted to an integer") });
    }
    let t = x.trunc();
    if t.abs() >= 9.2e18 {
        return Err(AbepError::OutOfDomain { message: format!("{what} = {x} is out of the integer range") });
    }
    Ok(t as i64)
}

/// `np.searchsorted(a, x)` (side='left') on a sorted slice: the number of elements strictly less than `x`.
pub fn searchsorted_left(a: &[f64], x: f64) -> usize {
    a.partition_point(|v| *v < x)
}

/// `np.interp(x, xp, fp)` for a scalar `x` (default left / right values `fp[0]` / `fp[-1]`; numpy's operation order:
/// `slope * (x - xp[j]) + fp[j]`, exact at nodes).
pub fn np_interp(x: f64, xp: &[f64], fp: &[f64]) -> f64 {
    let n = xp.len();
    if x.is_nan() {
        return x;
    }
    if x < xp[0] {
        return fp[0];
    }
    if x > xp[n - 1] {
        return fp[n - 1];
    }
    // largest j with xp[j] <= x
    let j = xp.partition_point(|v| *v <= x) - 1;
    if j == n - 1 || xp[j] == x {
        return fp[j];
    }
    let slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    let r = slope * (x - xp[j]) + fp[j];
    if r.is_nan() {
        let r2 = slope * (x - xp[j + 1]) + fp[j + 1];
        if r2.is_nan() && fp[j] == fp[j + 1] {
            return fp[j];
        }
        return r2;
    }
    r
}

/// Python `format(x, 'g')` (precision 6): fixed notation for exponents -4..5, else `d.ddddde+XX`; trailing zeros and
/// a trailing point are removed.
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

/// Python `format(x, '+.4f')`.
pub fn py_format_plus_4f(x: f64) -> String {
    format!("{x:+.4}")
}

/// Python `round(x, 6)` (correct rounding of the binary value to 6 decimals).
pub fn py_round6(x: f64) -> f64 {
    if !x.is_finite() || x == x.trunc() {
        return x;
    }
    format!("{x:.6}").parse().expect("formatted float")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn remainder_and_floor_division_follow_cpython() {
        assert_eq!(py_mod(-1.0, 24.0), 23.0);
        assert_eq!(py_mod(25.0, 24.0), 1.0);
        assert!(py_mod(-0.0, 24.0).is_sign_positive());
        assert_eq!(py_mod(-180.0, 360.0), 180.0);
        assert_eq!(py_floordiv(23.9, 24.0), 0.0);
        assert_eq!(py_floordiv(24.0, 24.0), 1.0);
        assert_eq!(py_floordiv(-0.5, 24.0), -1.0);
        assert!(py_floordiv(f64::INFINITY, 24.0).is_nan());
    }

    #[test]
    fn format_g_matches_the_python_specification() {
        for (x, s) in [
            (200.0, "200"),
            (195.5, "195.5"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (100000.0, "100000"),
            (1000000.0, "1e+06"),
            (123456789.0, "1.23457e+08"),
            (180.123456789, "180.123"),
            (-90.0, "-90"),
            (999999.5, "1e+06"),
        ] {
            assert_eq!(py_format_g(x), s, "{x}");
        }
        assert_eq!(py_format_plus_4f(37.0), "+37.0000");
        assert_eq!(py_format_plus_4f(-83.0), "-83.0000");
        assert_eq!(py_format_plus_4f(0.0), "+0.0000");
    }

    #[test]
    fn interp_is_exact_at_nodes_and_clamps() {
        let xp = [1.0, 2.0, 4.0];
        let fp = [10.0, 20.0, 0.0];
        assert_eq!(np_interp(2.0, &xp, &fp), 20.0);
        assert_eq!(np_interp(4.0, &xp, &fp), 0.0);
        assert_eq!(np_interp(3.0, &xp, &fp), 10.0);
        assert_eq!(np_interp(0.0, &xp, &fp), 10.0);
        assert_eq!(searchsorted_left(&xp, 2.0), 1);
        assert_eq!(searchsorted_left(&xp, 2.5), 2);
    }

    #[test]
    fn int_conversion_refuses_non_finite() {
        assert_eq!(py_int(10.9, "x").unwrap(), 10);
        assert_eq!(py_int(-10.9, "x").unwrap(), -10);
        assert!(py_int(f64::NAN, "x").is_err());
        assert!(py_int(f64::INFINITY, "x").is_err());
    }
}
