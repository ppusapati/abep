//! CPython 3.11 float semantics the SC-WP-08 kernels depend on: `float ** float` (float_pow, errno mapping),
//! `math.exp` / `math.log` / `math.sqrt` refusals, `/` by zero, `max(x, 0.0)`, and int / float numbers as they come
//! from the reference literals (an int stays an int in `dataclasses.asdict`).
//!
//! The libm calls go through `std::hint::black_box`, so the optimiser cannot replace `pow(x, c)` by another
//! expression: the call is the same glibc routine the reference interpreter makes.

use abep_types::pyjson::{py_repr, PyException, PyResult, Value};

pub fn err(class: &'static str, message: impl Into<String>) -> PyException {
    PyException::new(class, message)
}

/// `a / b` of two floats (`ZeroDivisionError: float division by zero`).
pub fn fdiv(a: f64, b: f64) -> PyResult<f64> {
    if b == 0.0 {
        return Err(err("ZeroDivisionError", "float division by zero"));
    }
    Ok(a / b)
}

/// `math.exp(x)`; an overflow from a finite argument raises `OverflowError: math range error`.
pub fn exp(x: f64) -> PyResult<f64> {
    let r = std::hint::black_box(x).exp();
    if r.is_infinite() && x.is_finite() {
        return Err(err("OverflowError", "math range error"));
    }
    Ok(r)
}

/// `math.log(x)` (natural log): `ValueError: math domain error` for x <= 0.
pub fn log(x: f64) -> PyResult<f64> {
    if x <= 0.0 {
        return Err(err("ValueError", "math domain error"));
    }
    Ok(std::hint::black_box(x).ln())
}

/// `math.sqrt(x)`: `ValueError: math domain error` for x < 0.
pub fn sqrt(x: f64) -> PyResult<f64> {
    if x < 0.0 {
        return Err(err("ValueError", "math domain error"));
    }
    Ok(std::hint::black_box(x).sqrt())
}

fn is_odd_integer(y: f64) -> bool {
    y.is_finite() && y.fract() == 0.0 && (y / 2.0).fract() != 0.0
}

/// `x ** y` of two Python floats (CPython `float_pow`).
pub fn pow(x: f64, y: f64) -> PyResult<f64> {
    if y == 0.0 {
        return Ok(1.0);
    }
    if x.is_nan() {
        return Ok(x);
    }
    if y.is_nan() {
        return Ok(if x == 1.0 { 1.0 } else { y });
    }
    if y.is_infinite() {
        let ax = x.abs();
        return Ok(if ax == 1.0 {
            1.0
        } else if (y > 0.0) == (ax > 1.0) {
            f64::INFINITY
        } else {
            0.0
        });
    }
    if x.is_infinite() {
        let odd = is_odd_integer(y);
        return Ok(if y > 0.0 {
            if odd {
                x
            } else {
                x.abs()
            }
        } else if odd {
            0.0f64.copysign(x)
        } else {
            0.0
        });
    }
    if x == 0.0 {
        if y < 0.0 {
            return Err(err("ZeroDivisionError", "0.0 cannot be raised to a negative power"));
        }
        return Ok(if is_odd_integer(y) { x } else { 0.0 });
    }
    let mut base = x;
    let mut negate = false;
    if x < 0.0 {
        if y.fract() != 0.0 {
            // CPython returns a complex number here; no registered kernel reaches it (contract domain notes).
            return Err(err("ComplexResult", "negative number cannot be raised to a fractional power"));
        }
        base = -x;
        negate = is_odd_integer(y);
    }
    if base == 1.0 {
        return Ok(if negate { -1.0 } else { 1.0 });
    }
    let r = std::hint::black_box(base).powf(std::hint::black_box(y));
    if r.is_infinite() {
        return Err(err("OverflowError", "(34, 'Numerical result out of range')"));
    }
    Ok(if negate { -r } else { r })
}

/// `max(x, 0.0)`: the first argument unless the second is greater (NaN stays NaN).
pub fn max_zero(x: f64) -> f64 {
    if 0.0 > x {
        0.0
    } else {
        x
    }
}

/// A number of a reference literal or a JSON input: Python keeps int and float apart.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Num {
    Int(i64),
    Float(f64),
}

impl Num {
    pub fn f(self) -> f64 {
        match self {
            Num::Int(i) => i as f64,
            Num::Float(x) => x,
        }
    }

    pub fn to_value(self) -> Value {
        match self {
            Num::Int(i) => Value::int(i),
            Num::Float(x) => Value::Float(x),
        }
    }

    /// A reference literal: '.', 'e' or 'E' makes a float (Python literal rules), otherwise an int; digit-group
    /// underscores are allowed, as in Python.
    pub fn parse_literal(text: &str) -> Num {
        let t = text.trim().replace('_', "");
        let t = t.as_str();
        if t.contains(['.', 'e', 'E']) {
            Num::Float(t.parse().expect("float literal"))
        } else {
            Num::Int(t.parse().expect("int literal"))
        }
    }

    /// A JSON number (bool counts as int, as in Python arithmetic). Other values raise `TypeError` with `what`.
    pub fn from_value(v: &Value, what: &str) -> PyResult<Num> {
        match v {
            Value::Bool(b) => Ok(Num::Int(i64::from(*b))),
            Value::Int(i) => i.as_i64().map(Num::Int).ok_or_else(|| err("OverflowError", "int too large")),
            Value::Float(x) => Ok(Num::Float(*x)),
            other => Err(err(
                "TypeError",
                format!("{what}: unsupported operand type '{}' ({})", other.type_name(), py_repr(other)),
            )),
        }
    }

    /// `a / b` (true division; `ZeroDivisionError` with the int or float message).
    pub fn true_div(a: Num, b: Num) -> PyResult<f64> {
        match (a, b) {
            (Num::Int(_), Num::Int(0)) => Err(err("ZeroDivisionError", "division by zero")),
            _ => fdiv(a.f(), b.f()),
        }
    }

    /// `-x` (an int stays an int, so `-0` is `0`).
    pub fn py_neg(self) -> Num {
        match self {
            Num::Int(i) => Num::Int(-i),
            Num::Float(x) => Num::Float(-x),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_pow_matches_cpython_special_cases() {
        assert_eq!(pow(0.93, -1e5).unwrap_err().class, "OverflowError");
        assert_eq!(pow(0.93, 1e9).unwrap(), 0.0);
        assert_eq!(pow(0.0, -1.0).unwrap_err().class, "ZeroDivisionError");
        assert_eq!(pow(-2.0, 3.0).unwrap(), -8.0);
        assert_eq!(pow(f64::NAN, 0.0).unwrap(), 1.0);
        assert_eq!(pow(1.0, f64::NAN).unwrap(), 1.0);
        assert!(pow(-2.0, 0.5).is_err());
        assert_eq!(exp(1000.0).unwrap_err().class, "OverflowError");
        assert_eq!(exp(-1000.0).unwrap(), 0.0);
        assert_eq!(max_zero(-0.0).to_bits(), (-0.0f64).to_bits());
        assert_eq!(Num::parse_literal("2700"), Num::Int(2700));
        assert_eq!(Num::parse_literal("2_700"), Num::Int(2700));
        assert_eq!(Num::parse_literal("1e6"), Num::Float(1e6));
        assert_eq!(Num::true_div(Num::Int(1), Num::Int(0)).unwrap_err().message, "division by zero");
    }
}
