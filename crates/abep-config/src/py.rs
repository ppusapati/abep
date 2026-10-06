//! Python object semantics over JSON-shaped values, so that a malformed document fails with the same exception
//! class as the Python reference (`dict.get` on a list is an `AttributeError`, `d[k]` a `KeyError`, ...).

use crate::{ConfigError, ConfigResult};
use abep_types::pyjson::{py_repr, py_repr_str, Dict, Value};

pub(crate) static NONE: Value = Value::Null;
pub(crate) static EMPTY_DICT: Value = Value::Dict(Dict::new());

pub(crate) fn type_error(msg: impl Into<String>) -> ConfigError {
    ConfigError::new("TypeError", msg)
}

pub(crate) fn key_error(key: &str) -> ConfigError {
    ConfigError::new("KeyError", py_repr_str(key))
}

fn attribute_error(v: &Value, name: &str) -> ConfigError {
    ConfigError::new("AttributeError", format!("'{}' object has no attribute '{name}'", v.type_name()))
}

/// `v.get(key)`.
pub(crate) fn get<'a>(v: &'a Value, key: &str) -> ConfigResult<&'a Value> {
    match v {
        Value::Dict(d) => Ok(d.get(key).unwrap_or(&NONE)),
        other => Err(attribute_error(other, "get")),
    }
}

/// `v[key]` with a str key.
pub(crate) fn index<'a>(v: &'a Value, key: &str) -> ConfigResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(key).ok_or_else(|| key_error(key)),
        Value::List(_) => Err(type_error("list indices must be integers or slices, not str")),
        Value::Str(_) => Err(type_error("string indices must be integers, not 'str'")),
        other => Err(type_error(format!("'{}' object is not subscriptable", other.type_name()))),
    }
}

/// `v or {}`.
pub(crate) fn or_empty(v: &Value) -> &Value {
    if v.truthy() {
        v
    } else {
        &EMPTY_DICT
    }
}

/// `v.items()`.
pub(crate) fn items(v: &Value) -> ConfigResult<&Dict> {
    match v {
        Value::Dict(d) => Ok(d),
        other => Err(attribute_error(other, "items")),
    }
}

/// `item in container`.
pub(crate) fn contains(container: &Value, item: &Value) -> ConfigResult<bool> {
    match container {
        Value::Dict(d) => match item {
            Value::List(_) | Value::Dict(_) => Err(type_error(format!("unhashable type: '{}'", item.type_name()))),
            Value::Str(s) => Ok(d.contains_key(s)),
            _ => Ok(false),
        },
        Value::List(l) => Ok(l.iter().any(|x| abep_types::pyjson::py_eq(x, item))),
        Value::Str(s) => match item {
            Value::Str(sub) => Ok(s.contains(sub.as_str())),
            other => {
                Err(type_error(format!("'in <string>' requires string as left operand, not {}", other.type_name())))
            }
        },
        other => Err(type_error(format!("argument of type '{}' is not iterable", other.type_name()))),
    }
}

pub(crate) fn contains_str(container: &Value, item: &str) -> ConfigResult<bool> {
    contains(container, &Value::str(item))
}

/// `list(v)` / `for x in v`.
pub(crate) fn iterate(v: &Value) -> ConfigResult<Vec<Value>> {
    match v {
        Value::List(l) => Ok(l.clone()),
        Value::Dict(d) => Ok(d.keys().map(|k| Value::str(k.as_str())).collect()),
        Value::Str(s) => Ok(s.chars().map(|c| Value::Str(c.to_string())).collect()),
        other => Err(type_error(format!("'{}' object is not iterable", other.type_name()))),
    }
}

/// `v == "s"`.
pub(crate) fn is_str(v: &Value, s: &str) -> bool {
    matches!(v, Value::Str(x) if x == s)
}

/// `repr(v)` (for messages).
pub(crate) fn r(v: &Value) -> String {
    py_repr(v)
}

/// `configuration._num_field(d, key, what)`.
pub(crate) fn num_field(d: &Value, key: &str, what: &str) -> ConfigResult<f64> {
    let Value::Dict(dd) = d else {
        return Err(ConfigError::configuration(format!("{what}: field {} missing", py_repr_str(key))));
    };
    let Some(v) = dd.get(key) else {
        return Err(ConfigError::configuration(format!("{what}: field {} missing", py_repr_str(key))));
    };
    if !v.is_number() {
        return Err(ConfigError::configuration(format!("{what}.{key}: non-numeric value {}", py_repr(v))));
    }
    Ok(v.to_f64()?)
}

/// `str(path_or_value)` joined to a root, as `Path / value` (only str is a valid operand).
pub(crate) fn path_operand(v: &Value) -> ConfigResult<&str> {
    match v {
        Value::Str(s) => Ok(s),
        other => Err(type_error(format!("unsupported operand type(s) for /: 'PosixPath' and '{}'", other.type_name()))),
    }
}

/// `x.startswith(prefix)` on a value that must be a str.
pub(crate) fn startswith(v: &Value, prefix: &str) -> ConfigResult<bool> {
    match v {
        Value::Str(s) => Ok(s.starts_with(prefix)),
        other => Err(attribute_error(other, "startswith")),
    }
}

/// Python `len(v)`.
pub(crate) fn len(v: &Value) -> ConfigResult<usize> {
    match v {
        Value::List(l) => Ok(l.len()),
        Value::Dict(d) => Ok(d.len()),
        Value::Str(s) => Ok(s.chars().count()),
        other => Err(type_error(format!("object of type '{}' has no len()", other.type_name()))),
    }
}
