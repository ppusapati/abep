//! Python float formatting used by the mass builders: `format(x, '.Ng')`, `format(x, '.Nf')` and the rounding
//! helpers `rk(x) = float(f"{x:.10g}")` / `sig6(x) = float(f"{x:.6g}")`.
//!
//! Rust's `{:.Ne}` / `{:.N}` produce the correctly rounded digits with ties to even, the same digits as CPython's
//! `float.__format__`; only the exponent spelling and the special values differ and are rewritten here.

/// `format(x, f'.{precision}g')` (precision 0 is treated as 1, as Python).
pub fn format_g(x: f64, precision: usize) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let p = precision.max(1);
    if x == 0.0 {
        return if x.is_sign_negative() { "-0".into() } else { "0".into() };
    }
    let sci = format!("{:.*e}", p - 1, x);
    let (mant, exp) = sci.split_once('e').expect("LowerExp has an exponent");
    let exp: i32 = exp.parse().expect("integer exponent");
    if exp >= -4 && exp < p as i32 {
        strip_zeros(&format!("{:.*}", (p as i32 - 1 - exp) as usize, x))
    } else {
        let m = strip_zeros(mant);
        format!("{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    }
}

fn strip_zeros(s: &str) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s.to_string()
    }
}

/// `format(x, f'.{decimals}f')`.
pub fn format_fixed(x: f64, decimals: usize) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    format!("{x:.decimals$}")
}

/// `float(format(x, f'.{sig}g'))`: the double nearest to x rounded to `sig` significant digits.
pub fn round_sig(x: f64, sig: usize) -> f64 {
    if !x.is_finite() || x == 0.0 {
        return x;
    }
    format!("{:.*e}", sig.max(1) - 1, x).parse().expect("formatted float parses")
}

/// `rk(x) = float(f"{x:.10g}")` (mass / power v3 and Xe accounting v3 builders).
pub fn rk(x: f64) -> f64 {
    round_sig(x, 10)
}

/// `sig6(x) = float(f"{x:.6g}")` (Xe accounting v3 builder).
pub fn sig6(x: f64) -> f64 {
    round_sig(x, 6)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn g_format_matches_python() {
        for (x, p, want) in [
            (38.34901052, 6, "38.349"),
            (1.743136842, 6, "1.74314"),
            (1.2, 6, "1.2"),
            (1.0, 6, "1"),
            (34.0, 6, "34"),
            (1e-05, 6, "1e-05"),
            (123456.0, 6, "123456"),
            (1234567.0, 6, "1.23457e+06"),
            (0.0001, 6, "0.0001"),
            (2.5e-07, 6, "2.5e-07"),
            (-0.0, 6, "-0"),
            (1234567890.5, 10, "1234567890"),
            (1234567891.5, 10, "1234567892"),
            (0.12345678905, 10, "0.1234567891"),
            (1e16, 10, "1e+16"),
        ] {
            assert_eq!(format_g(x, p), want, "{x} .{p}g");
        }
        assert_eq!(format_g(f64::NAN, 6), "nan");
    }

    #[test]
    fn rounding_helpers() {
        assert_eq!(rk(0.1 + 0.2), 0.3);
        assert_eq!(rk(-0.0).to_bits(), (-0.0f64).to_bits());
        assert_eq!(rk(1234567890.5), 1234567890.0);
        assert!(rk(f64::NAN).is_nan());
        assert_eq!(sig6(0.0392156862745098), 0.0392157);
        assert_eq!(format_fixed(0.34901052, 4), "0.3490");
        assert_eq!(format_fixed(38.34901052, 2), "38.35");
        assert_eq!(format_fixed(-0.0, 2), "-0.00");
    }
}
