//! CPython numeric and text semantics the SC-WP-05 references rely on: `math.fsum`, the `'g'` format presentation,
//! `float(str)`, `round()` half to even and the `_real` / `_nonempty` / `_keys` record checks.

use super::PowerError;
use abep_types::pyjson::{float_repr, py_repr, py_repr_str, py_strip, Dict, Value};

/// `math.fsum` of CPython 3.11 (Shewchuk partials, final half-even correction). A finite input sequence whose
/// running sum overflows raises `OverflowError('intermediate overflow in fsum')`; `inf - inf` raises `ValueError`.
pub fn fsum<I: IntoIterator<Item = f64>>(values: I) -> Result<f64, PowerError> {
    let mut p: Vec<f64> = Vec::new();
    let mut special_sum = 0.0_f64;
    let mut inf_sum = 0.0_f64;
    let mut lo = 0.0_f64;
    for item in values {
        let mut x = item;
        let xsave = x;
        let mut i = 0;
        for j in 0..p.len() {
            let mut y = p[j];
            if x.abs() < y.abs() {
                std::mem::swap(&mut x, &mut y);
            }
            let hi = x + y;
            let yr = hi - x;
            lo = y - yr;
            if lo != 0.0 {
                p[i] = lo;
                i += 1;
            }
            x = hi;
        }
        p.truncate(i);
        if x != 0.0 {
            if !x.is_finite() {
                if xsave.is_finite() {
                    return Err(PowerError::new("OverflowError", "intermediate overflow in fsum"));
                }
                if xsave.is_infinite() {
                    inf_sum += xsave;
                }
                special_sum += xsave;
                p.clear();
            } else {
                p.push(x);
            }
        }
    }
    if special_sum != 0.0 {
        if inf_sum.is_nan() {
            return Err(PowerError::new("ValueError", "-inf + inf in fsum"));
        }
        return Ok(special_sum);
    }
    let mut hi = 0.0_f64;
    let mut n = p.len();
    if n > 0 {
        n -= 1;
        hi = p[n];
        while n > 0 {
            let x = hi;
            n -= 1;
            let y = p[n];
            hi = x + y;
            let yr = hi - x;
            lo = y - yr;
            if lo != 0.0 {
                break;
            }
        }
        if n > 0 && ((lo < 0.0 && p[n - 1] < 0.0) || (lo > 0.0 && p[n - 1] > 0.0)) {
            let y = lo * 2.0;
            let x = hi + y;
            let yr = x - hi;
            if y == yr {
                hi = x;
            }
        }
    }
    Ok(hi)
}

/// Significant digits and decimal exponent of `|x|` rounded to `prec` digits (ties to even on the exact value, as
/// CPython's dtoa mode 2): returns (digits, exp) with |x| ~ d.ddd x 10^exp.
fn rounded_digits(ax: f64, prec: usize) -> (String, i32) {
    let s = format!("{:.*e}", prec - 1, ax);
    let (mant, exp) = s.split_once('e').expect("LowerExp always has an exponent");
    (mant.chars().filter(|c| *c != '.').collect(), exp.parse().expect("integer exponent"))
}

/// `format(x, f'.{prec}g')` of a Python float.
pub fn format_g(x: f64, prec: usize) -> String {
    let prec = prec.max(1);
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    if x == 0.0 {
        return format!("{sign}0");
    }
    let (digits, exp) = rounded_digits(x.abs(), prec);
    let body = if -4 <= exp && exp < prec as i32 {
        let digits = digits.as_bytes();
        let mut int_part = String::new();
        let mut frac = String::new();
        if exp >= 0 {
            let k = (exp + 1) as usize;
            for (i, d) in digits.iter().enumerate() {
                if i < k {
                    int_part.push(*d as char);
                } else {
                    frac.push(*d as char);
                }
            }
            while int_part.len() < k {
                int_part.push('0');
            }
        } else {
            int_part.push('0');
            frac.push_str(&"0".repeat((-exp - 1) as usize));
            frac.extend(digits.iter().map(|d| *d as char));
        }
        let frac = frac.trim_end_matches('0');
        if frac.is_empty() {
            int_part
        } else {
            format!("{int_part}.{frac}")
        }
    } else {
        let mant = digits.trim_end_matches('0');
        let mant = if mant.len() > 1 { format!("{}.{}", &mant[..1], &mant[1..]) } else { mant.to_string() };
        format!("{mant}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    format!("{sign}{body}")
}

/// `float(f"{x:.{n}g}")` (the P2 reducer's `_r`): `x` rounded to `n` significant digits, 0 and non-finite unchanged.
pub fn round_sig(x: f64, n: usize) -> f64 {
    if x == 0.0 || !x.is_finite() {
        return x;
    }
    let (digits, exp) = rounded_digits(x.abs(), n);
    let v: f64 = format!("0.{digits}e{}", exp + 1).parse().expect("decimal literal");
    if x < 0.0 {
        -v
    } else {
        v
    }
}

/// Python `float(text)` for an ASCII token without surrounding whitespace: optional sign, decimal digits with single
/// underscores between digits, optional fraction and exponent, or `inf` / `infinity` / `nan` in any case. `None`
/// where Python raises `ValueError`.
pub fn py_float_from_str(text: &str) -> Option<f64> {
    let s = py_strip(text);
    let (neg, body) = match s.as_bytes().first() {
        Some(b'-') => (true, &s[1..]),
        Some(b'+') => (false, &s[1..]),
        _ => (false, s),
    };
    let low = body.to_ascii_lowercase();
    let special = match low.as_str() {
        "inf" | "infinity" => Some(f64::INFINITY),
        "nan" => Some(f64::NAN),
        _ => None,
    };
    if let Some(v) = special {
        return Some(if neg { -v } else { v });
    }
    let b = body.as_bytes();
    let mut i = 0;
    let digitpart = |i: &mut usize| -> Option<usize> {
        let start = *i;
        if *i >= b.len() || !b[*i].is_ascii_digit() {
            return None;
        }
        *i += 1;
        while *i < b.len() {
            if b[*i].is_ascii_digit() {
                *i += 1;
            } else if b[*i] == b'_' && *i + 1 < b.len() && b[*i + 1].is_ascii_digit() {
                *i += 2;
            } else {
                break;
            }
        }
        Some(*i - start)
    };
    let int_digits = digitpart(&mut i).is_some();
    let mut frac_digits = false;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        frac_digits = digitpart(&mut i).is_some();
    }
    if !int_digits && !frac_digits {
        return None;
    }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        digitpart(&mut i)?;
    }
    if i != b.len() {
        return None;
    }
    let clean: String = body.chars().filter(|c| *c != '_').collect();
    let v: f64 = clean.parse().ok()?;
    Some(if neg { -v } else { v })
}

/// `isinstance(v, numbers.Real) and not isinstance(v, bool)` for a JSON value.
pub fn is_real(v: &Value) -> bool {
    matches!(v, Value::Int(_) | Value::Float(_))
}

/// The references' `_real(value, what)`: a finite real number (an int is converted), `-0.0` normalised by `+ 0.0`.
pub fn real(v: &Value, what: &str, class: &'static str) -> Result<f64, PowerError> {
    if !is_real(v) {
        return Err(PowerError::new(
            class,
            format!("{what} must be a real number, got {} {}", v.type_name(), py_repr(v)),
        ));
    }
    let x = v.to_f64().map_err(PowerError::from)?;
    if !x.is_finite() {
        return Err(PowerError::new(class, format!("{what} must be finite, got {}", float_repr(x))));
    }
    Ok(x + 0.0)
}

/// The references' `_nonempty(rec, key, what)`.
pub fn nonempty(rec: &Dict, key: &str, what: &str, class: &'static str) -> Result<String, PowerError> {
    match rec.get(key) {
        Some(Value::Str(s)) if !py_strip(s).is_empty() => Ok(s.clone()),
        _ => Err(PowerError::new(class, format!("{what}: '{key}' must be a non-empty string"))),
    }
}

/// `repr(sorted(strings))` of a list of strings.
pub fn repr_str_list<S: AsRef<str>>(items: &[S]) -> String {
    format!("[{}]", items.iter().map(|s| py_repr_str(s.as_ref())).collect::<Vec<_>>().join(", "))
}

/// The references' `_keys(rec, allowed, what)`: refuse keys outside `allowed` (schema parity).
pub fn check_keys(rec: &Dict, allowed: &[&str], what: &str, class: &'static str) -> Result<(), PowerError> {
    let mut extra: Vec<&String> = rec.keys().filter(|k| !allowed.contains(&k.as_str())).collect();
    if extra.is_empty() {
        return Ok(());
    }
    extra.sort();
    let mut allowed_sorted: Vec<&str> = allowed.to_vec();
    allowed_sorted.sort_unstable();
    Err(PowerError::new(
        class,
        format!(
            "{what}: unexpected key(s) {}; allowed {} (schema parity)",
            repr_str_list(&extra),
            repr_str_list(&allowed_sorted)
        ),
    ))
}

/// `isinstance(v, str) or not isinstance(v, Sequence)` is false: a JSON list.
pub fn as_sequence(v: &Value) -> Option<&[Value]> {
    match v {
        Value::List(l) => Some(l),
        _ => None,
    }
}

/// Python's `not a > b` (true when either operand is NaN).
#[allow(clippy::neg_cmp_op_on_partial_ord)]
pub fn py_not_gt(a: f64, b: f64) -> bool {
    !(a > b)
}

/// Python's `not a < b` (true when either operand is NaN).
#[allow(clippy::neg_cmp_op_on_partial_ord)]
pub fn py_not_lt(a: f64, b: f64) -> bool {
    !(a < b)
}

/// Opaque operands for libm calls: the optimiser may not rewrite `pow(x, c)` into another expression, so the call
/// is the same libm `pow` the reference interpreter makes.
pub fn libm_pow(x: f64, y: f64) -> f64 {
    std::hint::black_box(x).powf(std::hint::black_box(y))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fsum_is_correctly_rounded_and_overflow_refused() {
        assert_eq!(fsum([1e-16, 1.0, 1e16]).unwrap(), 10000000000000002.0);
        assert_eq!(fsum([0.1; 10]).unwrap(), 1.0);
        assert_eq!(fsum(std::iter::empty()).unwrap(), 0.0);
        let e = fsum([1.6e308, 1.6e308]).unwrap_err();
        assert_eq!((e.class, e.message.as_str()), ("OverflowError", "intermediate overflow in fsum"));
        assert!(fsum([f64::NAN, 1.0]).unwrap().is_nan());
        assert_eq!(fsum([f64::INFINITY, -f64::INFINITY]).unwrap_err().class, "ValueError");
    }

    #[test]
    fn g_format_matches_python() {
        for (x, p, s) in [
            (0.30000000000000004, 4, "0.3"),
            (1234.5, 4, "1234"),
            (12345.0, 4, "1.234e+04"),
            (0.0001234565, 4, "0.0001235"),
            (0.00001234, 4, "1.234e-05"),
            (2.5, 1, "2"),
            (100.0, 3, "100"),
            (-0.0, 4, "-0"),
            (1e300, 4, "1e+300"),
            (f64::NAN, 4, "nan"),
            (0.5, 3, "0.5"),
        ] {
            assert_eq!(format_g(x, p), s, "{x} .{p}g");
        }
    }

    #[test]
    fn float_parse_follows_python_float() {
        assert_eq!(py_float_from_str("1_000"), Some(1000.0));
        assert_eq!(py_float_from_str("5_0"), Some(50.0));
        assert_eq!(py_float_from_str("1__0"), None);
        assert_eq!(py_float_from_str("_1"), None);
        assert_eq!(py_float_from_str("1_"), None);
        assert_eq!(py_float_from_str("+50."), Some(50.0));
        assert_eq!(py_float_from_str("-0.e0"), Some(-0.0));
        assert_eq!(py_float_from_str(".5"), Some(0.5));
        assert_eq!(py_float_from_str("."), None);
        assert_eq!(py_float_from_str("1e"), None);
        assert_eq!(py_float_from_str("Infinity"), Some(f64::INFINITY));
        assert!(py_float_from_str("-NaN").unwrap().is_nan());
        assert_eq!(py_float_from_str("1e400"), Some(f64::INFINITY));
        assert_eq!(py_float_from_str("0x10"), None);
        assert_eq!(py_float_from_str("abc"), None);
    }

    #[test]
    fn round_sig_is_nine_significant_digits() {
        assert_eq!(round_sig(0.1234567891234, 9), 0.123456789);
        assert_eq!(round_sig(-123456789.5, 9), -123456790.0);
        assert_eq!(round_sig(0.0, 9), 0.0);
    }
}
