//! Python value semantics the ported assessment functions rely on (dict access, truthiness, `format(x, '.6g')`).

use crate::error::{key_error, AssessError, AssessResult};
use abep_types::pyjson::{py_repr, Dict, Value};

pub use abep_subsystems::mass::pyfmt::format_g;

pub fn s(x: impl Into<String>) -> Value {
    Value::Str(x.into())
}

pub fn strs(xs: &[&str]) -> Value {
    Value::List(xs.iter().map(|x| s(*x)).collect())
}

fn attr_error(v: &Value, attr: &str) -> AssessError {
    AssessError::new("AttributeError", format!("'{}' object has no attribute '{attr}'", v.type_name()))
}

/// `d[key]` (KeyError when absent; TypeError on a non-dict).
pub fn get<'a>(v: &'a Value, key: &str) -> AssessResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(key).ok_or_else(|| key_error(key)),
        other => Err(AssessError::new(
            "TypeError",
            format!("{} indices must be integers or slices, not str", other.type_name()),
        )),
    }
}

/// `d.get(key)` (None when absent; AttributeError on a non-dict).
pub fn dget(v: &Value, key: &str) -> AssessResult<Value> {
    match v {
        Value::Dict(d) => Ok(d.get(key).cloned().unwrap_or(Value::Null)),
        other => Err(attr_error(other, "get")),
    }
}

/// `d.get(key, default)`.
pub fn dget_or(v: &Value, key: &str, default: Value) -> AssessResult<Value> {
    match v {
        Value::Dict(d) => Ok(d.get(key).cloned().unwrap_or(default)),
        other => Err(attr_error(other, "get")),
    }
}

pub fn as_dict(v: &Value) -> AssessResult<&Dict> {
    v.as_dict().ok_or_else(|| attr_error(v, "get"))
}

/// `list(x)` of a JSON list (anything else is outside the documented shapes).
pub fn as_list(v: &Value) -> AssessResult<&[Value]> {
    v.as_list().ok_or_else(|| AssessError::new("TypeError", format!("'{}' object is not a list", v.type_name())))
}

pub fn eq_str(v: &Value, x: &str) -> bool {
    matches!(v, Value::Str(t) if t == x)
}

pub fn in_strs(v: &Value, xs: &[&str]) -> bool {
    xs.iter().any(|x| eq_str(v, x))
}

/// `upstream_a9_13._finite`: an int or float (not bool) with a finite value.
pub fn finite(v: &Value) -> bool {
    match v {
        Value::Int(i) => i.to_f64().map(f64::is_finite).unwrap_or(false),
        Value::Float(f) => f.is_finite(),
        _ => false,
    }
}

/// `float(v)` of a number or bool.
pub fn float(v: &Value) -> AssessResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => Ok(v.to_f64()?),
        other => Err(AssessError::new(
            "TypeError",
            format!("float() argument must be a string or a real number, not '{}'", other.type_name()),
        )),
    }
}

/// `format(v, '.6g')` of an int or float record value.
pub fn fmt6g(v: &Value) -> AssessResult<String> {
    Ok(format_g(float(v)?, 6))
}

/// `format(x, 'g')`.
pub fn fmt_g(x: f64) -> String {
    format_g(x, 6)
}

/// `str(x)` (`py_str`) re-exported for f-string fields.
pub fn py_str(v: &Value) -> String {
    abep_types::pyjson::py_str(v)
}

/// `f"{x!r:.80}"`: the repr truncated to n code points.
pub fn repr_trunc(v: &Value, n: usize) -> String {
    py_repr(v).chars().take(n).collect()
}

/// Build an ordered dict from pairs.
pub fn dict(pairs: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in pairs {
        d.insert(k, v);
    }
    Value::Dict(d)
}
