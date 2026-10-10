//! Python argument semantics shared by the ported interfaces: refusals keyed by the reference exception class,
//! `float(x)`, the `_req_pos` check of spacecraft_reference_drag and dict access with KeyError.

use abep_types::pyjson::{py_repr, py_repr_str, py_strip, Dict, PyException, Value};
use abep_types::{AbepError, AbepResult};

/// Refusal carrying the reference exception class as message key (`<class>: <text>`), status OUT_OF_DOMAIN.
pub(crate) fn py_err(class: &str, text: impl std::fmt::Display) -> AbepError {
    AbepError::OutOfDomain { message: format!("{class}: {text}") }
}

pub(crate) fn from_py(e: PyException) -> AbepError {
    py_err(e.class, e.message)
}

/// `KeyError(key)`: str() of a KeyError is the repr of its argument.
pub(crate) fn key_error(key: &str) -> AbepError {
    py_err("KeyError", py_repr_str(key))
}

/// The reference exception class of a refusal produced by this crate (`ValueError`, `TypeError`, ...).
pub fn error_class(e: &AbepError) -> Option<&str> {
    match e {
        AbepError::OutOfDomain { message } | AbepError::Model { message } => message.split_once(": ").map(|(k, _)| k),
        _ => None,
    }
}

/// `isinstance(x, (int, float)) and not isinstance(x, bool)`.
pub(crate) fn is_number(v: &Value) -> bool {
    matches!(v, Value::Int(_) | Value::Float(_))
}

/// `float(v)` for a JSON-shaped value: numbers and bools convert; a string follows the Python float() grammar for
/// decimal, inf and nan literals (contract DIV-B-02); anything else is the reference TypeError.
pub(crate) fn py_float(v: &Value) -> AbepResult<f64> {
    match v {
        Value::Int(i) => i.to_f64().map_err(from_py),
        Value::Float(f) => Ok(*f),
        Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
        Value::Str(s) => parse_py_float(s)
            .ok_or_else(|| py_err("ValueError", format!("could not convert string to float: {}", py_repr_str(s)))),
        other => Err(py_err(
            "TypeError",
            format!("float() argument must be a string or a real number, not '{}'", other.type_name()),
        )),
    }
}

fn parse_py_float(s: &str) -> Option<f64> {
    let t = py_strip(s);
    let (sign, body) = match t.strip_prefix('-') {
        Some(b) => (-1.0, b),
        None => (1.0, t.strip_prefix('+').unwrap_or(t)),
    };
    match body.to_ascii_lowercase().as_str() {
        "inf" | "infinity" => return Some(sign * f64::INFINITY),
        "nan" => return Some(f64::NAN),
        _ => {}
    }
    let b = body.as_bytes();
    // underscores only between digits, as Python's float() grammar
    for (i, c) in b.iter().enumerate() {
        if *c == b'_' && !(i > 0 && i + 1 < b.len() && b[i - 1].is_ascii_digit() && b[i + 1].is_ascii_digit()) {
            return None;
        }
    }
    let cleaned: String = body.chars().filter(|c| *c != '_').collect();
    if cleaned.is_empty()
        || !cleaned.bytes().all(|c| c.is_ascii_digit() || matches!(c, b'.' | b'e' | b'E' | b'+' | b'-'))
    {
        return None;
    }
    cleaned.parse::<f64>().ok().map(|x| sign * x)
}

/// `_req_pos(name, x, allow_zero)` of spacecraft_reference_drag: required, a number (not bool), finite, >= 0 and,
/// unless `allow_zero`, > 0.
pub(crate) fn req_pos(name: &str, x: &Value, allow_zero: bool) -> AbepResult<f64> {
    if matches!(x, Value::Null) {
        return Err(py_err("ValueError", format!("{name} is required (no default)")));
    }
    if !is_number(x) {
        return Err(py_err("TypeError", format!("{name} must be a number")));
    }
    let xf = py_float(x)?;
    if !xf.is_finite() || xf < 0.0 || (xf == 0.0 && !allow_zero) {
        let bound = if allow_zero { ">= 0" } else { "> 0" };
        return Err(py_err("ValueError", format!("{name} must be finite and {bound}; got {}", py_repr(x))));
    }
    Ok(xf)
}

/// `isinstance(s, str) and s.strip()`.
pub(crate) fn nonblank_str(v: &Value) -> bool {
    matches!(v, Value::Str(s) if !py_strip(s).is_empty())
}

/// `d[key]` with the reference KeyError.
pub(crate) fn get<'a>(d: &'a Dict, key: &str) -> AbepResult<&'a Value> {
    d.get(key).ok_or_else(|| key_error(key))
}

/// `d.get(key)` (None when absent).
pub(crate) fn get_or_null<'a>(d: &'a Dict, key: &str) -> &'a Value {
    const NULL: Value = Value::Null;
    d.get(key).unwrap_or(&NULL)
}

/// Python `a - b` / `a + b` operand check for a JSON value used as a number (int, float or bool).
pub(crate) fn operand(v: &Value, op: char, left: &str) -> AbepResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => py_float(v),
        other => Err(py_err(
            "TypeError",
            format!("unsupported operand type(s) for {op}: '{left}' and '{}'", other.type_name()),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn req_pos_follows_the_reference_rules() {
        assert_eq!(req_pos("x", &Value::Float(2.5), false).unwrap(), 2.5);
        assert_eq!(req_pos("x", &Value::int(3), false).unwrap(), 3.0);
        assert_eq!(req_pos("x", &Value::Float(0.0), true).unwrap(), 0.0);
        let msg = |r: AbepResult<f64>| r.unwrap_err().to_string();
        assert!(msg(req_pos("x", &Value::Null, false)).ends_with("ValueError: x is required (no default)"));
        assert!(msg(req_pos("x", &Value::Bool(true), false)).ends_with("TypeError: x must be a number"));
        assert!(msg(req_pos("x", &Value::int(0), false)).ends_with("ValueError: x must be finite and > 0; got 0"));
        assert!(msg(req_pos("x", &Value::Float(-1.0), true)).ends_with("must be finite and >= 0; got -1.0"));
        assert!(msg(req_pos("x", &Value::Float(f64::NAN), true)).ends_with("got nan"));
    }

    #[test]
    fn float_of_strings_follows_python() {
        assert_eq!(py_float(&Value::str(" 1_0.5 ")).unwrap(), 10.5);
        assert_eq!(py_float(&Value::str("-inf")).unwrap(), f64::NEG_INFINITY);
        assert!(py_float(&Value::str("NaN")).unwrap().is_nan());
        let e = py_float(&Value::str("x")).unwrap_err().to_string();
        assert!(e.ends_with("ValueError: could not convert string to float: 'x'"), "{e}");
        assert!(py_float(&Value::str("1__0")).is_err());
        let e = py_float(&Value::Null).unwrap_err().to_string();
        assert!(e.ends_with("TypeError: float() argument must be a string or a real number, not 'NoneType'"));
    }
}
