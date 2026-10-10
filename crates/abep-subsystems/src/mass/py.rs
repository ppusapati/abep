//! CPython 3.11 semantics the mass builders rely on, over JSON-shaped values (`abep_types::pyjson::Value`):
//! subscripting with `KeyError` / `TypeError`, truthiness, numeric `==`, `sum()` (sequential double addition, as
//! CPython 3.11; 3.12+ uses compensated summation), `sorted()` on numbers / strings and `format()` specs.

use abep_types::pyjson::{float_repr, py_eq, py_repr, py_str, Dict, PyException, PyResult, Value};
use abep_types::{AbepError, EvalStatus};

pub fn err(class: &'static str, message: impl Into<String>) -> PyException {
    PyException::new(class, message)
}

/// A Python exception mirrored as the repository's fail-closed error (every refusal is MODEL_ERROR).
pub fn to_abep(e: PyException) -> AbepError {
    AbepError::Model { message: format!("{}: {}", e.class, e.message) }
}

/// Status of a refusal (always MODEL_ERROR: a refused input is never a value).
pub fn refusal_status(_e: &PyException) -> EvalStatus {
    EvalStatus::ModelError
}

pub fn s(text: impl Into<String>) -> Value {
    Value::Str(text.into())
}

pub fn f(x: f64) -> Value {
    Value::Float(x)
}

pub fn list<I: IntoIterator<Item = Value>>(items: I) -> Value {
    Value::List(items.into_iter().collect())
}

pub fn strs(items: &[&str]) -> Value {
    list(items.iter().map(|x| s(*x)))
}

/// `type(v).__name__` for messages.
fn tname(v: &Value) -> &'static str {
    v.type_name()
}

/// `v[key]` for a str key.
pub fn gi<'a>(v: &'a Value, key: &str) -> PyResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(key).ok_or_else(|| err("KeyError", abep_types::pyjson::py_repr_str(key))),
        Value::List(_) => Err(err("TypeError", "list indices must be integers or slices, not str")),
        Value::Str(_) => Err(err("TypeError", "string indices must be integers")),
        other => Err(err("TypeError", format!("'{}' object is not subscriptable", tname(other)))),
    }
}

/// `v[key]` for an arbitrary (hashable) key: dict lookup with Python key equality.
pub fn gi_val<'a>(v: &'a Value, key: &Value) -> PyResult<&'a Value> {
    match key {
        Value::Str(k) => gi(v, k),
        Value::List(_) | Value::Dict(_) => Err(err("TypeError", format!("unhashable type: '{}'", tname(key)))),
        _ => match v {
            Value::Dict(d) => d
                .iter()
                .find(|(k, _)| py_eq(&Value::Str((*k).clone()), key))
                .map(|(_, x)| x)
                .ok_or_else(|| err("KeyError", py_repr(key))),
            other => gi(other, ""),
        },
    }
}

/// `v.get(key, default)` (`AttributeError` when `v` is not a dict).
pub fn get<'a>(v: &'a Value, key: &str) -> PyResult<Option<&'a Value>> {
    match v {
        Value::Dict(d) => Ok(d.get(key)),
        other => Err(err("AttributeError", format!("'{}' object has no attribute 'get'", tname(other)))),
    }
}

/// `v.get(key)` with `None` for a missing key.
pub fn get_or_none(v: &Value, key: &str) -> PyResult<Value> {
    Ok(get(v, key)?.cloned().unwrap_or(Value::Null))
}

pub fn as_dict(v: &Value) -> PyResult<&Dict> {
    v.as_dict().ok_or_else(|| err("TypeError", format!("'{}' object is not a mapping", tname(v))))
}

pub fn as_dict_mut(v: &mut Value) -> &mut Dict {
    match v {
        Value::Dict(d) => d,
        _ => panic!("builder invariant: a dict was expected"),
    }
}

/// `iter(v)` for the shapes the builders iterate (a list; a dict iterates its keys).
pub fn iter(v: &Value) -> PyResult<Vec<Value>> {
    match v {
        Value::List(l) => Ok(l.clone()),
        Value::Dict(d) => Ok(d.keys().map(|k| Value::Str(k.clone())).collect()),
        Value::Str(t) => Ok(t.chars().map(|c| Value::Str(c.to_string())).collect()),
        other => Err(err("TypeError", format!("'{}' object is not iterable", tname(other)))),
    }
}

pub fn is_none(v: &Value) -> bool {
    matches!(v, Value::Null)
}

pub fn eq_str(v: &Value, text: &str) -> bool {
    matches!(v, Value::Str(x) if x == text)
}

/// `x in (a, b, ...)` (tuple membership: equality, numeric across int / float / bool).
pub fn in_tuple(v: &Value, items: &[Value]) -> bool {
    items.iter().any(|x| py_eq(v, x))
}

pub fn in_strs(v: &Value, items: &[&str]) -> bool {
    items.iter().any(|x| eq_str(v, x))
}

/// `float(v)` for an int / float / bool (the numbers the rules accept); `TypeError` otherwise.
pub fn num(v: &Value) -> PyResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => v.to_f64(),
        other => Err(err("TypeError", format!("unsupported operand type for a number: '{}'", tname(other)))),
    }
}

/// `isinstance(v, (int, float)) and not isinstance(v, bool)`.
pub fn is_real(v: &Value) -> bool {
    matches!(v, Value::Int(_) | Value::Float(_))
}

/// `sum(values)` for numbers (start 0, sequential double addition as CPython 3.11); `TypeError` on a non-number.
pub fn sum(values: &[Value]) -> PyResult<f64> {
    let mut acc = 0.0_f64;
    for v in values {
        acc += num(v)?;
    }
    Ok(acc)
}

/// `float.__repr__` / `str()` of a float, `str()` of any value.
pub fn repr_f(x: f64) -> String {
    float_repr(x)
}

pub fn pstr(v: &Value) -> String {
    py_str(v)
}

pub fn prepr(v: &Value) -> String {
    py_repr(v)
}

/// Python ordering of two numbers or two strings (`sorted()` keys of the builders); `TypeError` otherwise.
pub fn py_lt(a: &Value, b: &Value) -> PyResult<bool> {
    match (a, b) {
        (Value::Str(x), Value::Str(y)) => Ok(x < y),
        _ if is_number_like(a) && is_number_like(b) => Ok(num(a)? < num(b)?),
        _ => Err(err("TypeError", format!("'<' not supported between instances of '{}' and '{}'", tname(a), tname(b)))),
    }
}

fn is_number_like(v: &Value) -> bool {
    matches!(v, Value::Int(_) | Value::Float(_) | Value::Bool(_))
}

/// `sorted(items)` (stable merge sort with Python `<`).
pub fn sorted(items: &[Value]) -> PyResult<Vec<Value>> {
    let mut out: Vec<Value> = Vec::with_capacity(items.len());
    for it in items {
        let mut pos = out.len();
        while pos > 0 && py_lt(it, &out[pos - 1])? {
            pos -= 1;
        }
        out.insert(pos, it.clone());
    }
    Ok(out)
}

/// A Python dict built from (key, value) pairs: equal keys (2 == 2.0) collapse, the first key object keeps its
/// position and the last value wins.
pub fn dict_pairs(pairs: Vec<(Value, Value)>) -> Vec<(Value, Value)> {
    let mut out: Vec<(Value, Value)> = Vec::new();
    for (k, v) in pairs {
        match out.iter_mut().find(|(ek, _)| py_eq(ek, &k)) {
            Some(slot) => slot.1 = v,
            None => out.push((k, v)),
        }
    }
    out
}

/// `str.join` over items that must all be `str`.
pub fn join_strs(sep: &str, items: &[Value]) -> PyResult<String> {
    let mut parts = Vec::with_capacity(items.len());
    for (i, it) in items.iter().enumerate() {
        match it {
            Value::Str(t) => parts.push(t.as_str()),
            other => {
                return Err(err(
                    "TypeError",
                    format!("sequence item {i}: expected str instance, {} found", tname(other)),
                ))
            }
        }
    }
    Ok(parts.join(sep))
}

/// `format(v, 'g')` for a number value (bool / int are formatted as float, as `int.__format__` does for 'g');
/// `ValueError` for a str, `TypeError` for other types.
pub fn fmt_g_value(v: &Value) -> PyResult<String> {
    match v {
        Value::Int(_) | Value::Float(_) | Value::Bool(_) => Ok(super::pyfmt::format_g(num(v)?, 6)),
        Value::Str(_) => Err(err("ValueError", "Unknown format code 'g' for object of type 'str'")),
        other => Err(err("TypeError", format!("unsupported format string passed to {}.__format__", tname(other)))),
    }
}

/// Deep copy of a dict value with `entries` set (`dict(base, **entries)` / `d.update(entries)`): an existing key keeps
/// its position, a new key is appended.
pub fn updated(base: &Value, entries: Vec<(&str, Value)>) -> Value {
    let mut out = base.clone();
    let d = as_dict_mut(&mut out);
    for (k, v) in entries {
        d.insert(k, v);
    }
    out
}

/// `dict` built in literal order.
pub fn dict(entries: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in entries {
        d.insert(k, v);
    }
    Value::Dict(d)
}

/// Python `str.split()` (no argument) joined by single spaces: `" ".join(text.split())`.
pub fn norm_ws(text: &str) -> String {
    text.split(abep_types::pyjson::py_isspace).filter(|t| !t.is_empty()).collect::<Vec<_>>().join(" ")
}

/// Python `str.splitlines()[0]` (`IndexError` on an empty string).
pub fn first_line(text: &str) -> PyResult<&str> {
    if text.is_empty() {
        return Err(err("IndexError", "list index out of range"));
    }
    let boundary = |c: char| {
        matches!(
            c,
            '\n' | '\r' | '\u{0b}' | '\u{0c}' | '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{85}' | '\u{2028}' | '\u{2029}'
        )
    };
    Ok(match text.find(boundary) {
        Some(i) => &text[..i],
        None => text,
    })
}

/// `text.split(sep, 1)[1]` (`IndexError` when `sep` is absent).
pub fn after(text: &str, sep: &str) -> PyResult<String> {
    text.split_once(sep).map(|(_, b)| b.to_string()).ok_or_else(|| err("IndexError", "list index out of range"))
}

/// `text.split(sep, 1)[0]`.
pub fn before(text: &str, sep: &str) -> String {
    text.split_once(sep).map(|(a, _)| a.to_string()).unwrap_or_else(|| text.to_string())
}

/// Read a repository file's bytes (`FileNotFoundError` / `OSError` as Python).
pub fn read_bytes(repo: &std::path::Path, rel: &str) -> PyResult<Vec<u8>> {
    let p = repo.join(rel);
    std::fs::read(&p).map_err(|e| {
        let class = if e.kind() == std::io::ErrorKind::NotFound { "FileNotFoundError" } else { "OSError" };
        err(class, format!("{}: '{}'", e, p.display()))
    })
}

/// `Path.read_text(encoding="utf-8")`.
pub fn read_text(repo: &std::path::Path, rel: &str) -> PyResult<String> {
    abep_types::pyjson::read_text_utf8(&read_bytes(repo, rel)?)
}

/// `json.loads(Path.read_text(encoding="utf-8"))`.
pub fn load_json(repo: &std::path::Path, rel: &str) -> PyResult<Value> {
    abep_types::pyjson::loads(&read_text(repo, rel)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::pyjson::loads;

    #[test]
    fn subscripting_and_membership_follow_python() {
        let d = loads(r#"{"a": 1, "b": {"c": null}}"#).unwrap();
        assert_eq!(gi(&d, "a").unwrap(), &Value::int(1));
        assert_eq!(gi(&d, "z").unwrap_err().class, "KeyError");
        assert_eq!(gi(&Value::Null, "a").unwrap_err().class, "TypeError");
        assert!(in_tuple(&Value::int(0), &[Value::int(0), f(0.0)]));
        assert!(in_tuple(&Value::Bool(false), &[Value::int(0), f(0.0)]));
        assert!(!in_tuple(&f(f64::NAN), &[Value::int(0), f(0.0)]));
    }

    #[test]
    fn sum_sort_and_dict_semantics() {
        assert_eq!(sum(&[Value::int(1), f(0.5), Value::Bool(true)]).unwrap(), 2.5);
        assert_eq!(sum(&[s("x")]).unwrap_err().class, "TypeError");
        let got = sorted(&[f(5.0), Value::int(2), f(10.0), f(-0.0)]).unwrap();
        assert_eq!(got, vec![f(-0.0), Value::int(2), f(5.0), f(10.0)]);
        let d = dict_pairs(vec![(f(2.0), s("a")), (Value::int(2), s("b")), (f(5.0), s("c"))]);
        assert_eq!(d, vec![(f(2.0), s("b")), (f(5.0), s("c"))]);
        assert_eq!(norm_ws(" a\u{1c}b \n c "), "a b c");
        assert_eq!(first_line("x\u{2028}y").unwrap(), "x");
    }
}
