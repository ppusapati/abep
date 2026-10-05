//! Python value semantics for the checks the verifier reproduces: ordered dicts (file order, a duplicate key keeps its
//! first position and its last value, as `json.load`), int / float / bool distinction, `==`, `math.isclose`, `in`,
//! `float()`, `str()`, truthiness and subscription errors (KeyError / TypeError / IndexError).

use super::{Py, Raised};
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use std::fmt;

/// A JSON / TOML document value with Python semantics.
#[derive(Debug, Clone)]
pub enum PyValue {
    None,
    Bool(bool),
    Int(i128),
    Float(f64),
    Str(String),
    List(Vec<PyValue>),
    /// Insertion-ordered; keys are `Str` for JSON / TOML documents, any hashable value for built maps.
    Dict(Vec<(PyValue, PyValue)>),
    /// A TOML date / time (Python datetime / date / time); equal only to the same text.
    DateTime(String),
}

/// Python `==`.
impl PartialEq for PyValue {
    fn eq(&self, other: &Self) -> bool {
        self.py_eq(other)
    }
}

#[derive(Debug, Clone, Copy)]
enum Num {
    Int(i128),
    Float(f64),
}

fn num_eq(a: Num, b: Num) -> bool {
    match (a, b) {
        (Num::Int(x), Num::Int(y)) => x == y,
        (Num::Float(x), Num::Float(y)) => x == y,
        (Num::Int(i), Num::Float(f)) | (Num::Float(f), Num::Int(i)) => {
            // Python compares int and float exactly.
            f.is_finite() && f.fract() == 0.0 && f.abs() < 1.7e38 && (f as i128) == i
        }
    }
}

impl PyValue {
    pub fn str(s: impl Into<String>) -> Self {
        PyValue::Str(s.into())
    }

    /// Python type name, for error details.
    pub fn type_name(&self) -> &'static str {
        match self {
            PyValue::None => "NoneType",
            PyValue::Bool(_) => "bool",
            PyValue::Int(_) => "int",
            PyValue::Float(_) => "float",
            PyValue::Str(_) => "str",
            PyValue::List(_) => "list",
            PyValue::Dict(_) => "dict",
            PyValue::DateTime(_) => "datetime",
        }
    }

    fn num(&self) -> Option<Num> {
        match self {
            PyValue::Bool(b) => Some(Num::Int(i128::from(*b))),
            PyValue::Int(i) => Some(Num::Int(*i)),
            PyValue::Float(f) => Some(Num::Float(*f)),
            _ => None,
        }
    }

    /// `isinstance(x, (int, float))` (bool included, as in Python).
    pub fn is_number(&self) -> bool {
        self.num().is_some()
    }

    /// Python `==`.
    pub fn py_eq(&self, other: &PyValue) -> bool {
        if let (Some(a), Some(b)) = (self.num(), other.num()) {
            return num_eq(a, b);
        }
        match (self, other) {
            (PyValue::None, PyValue::None) => true,
            (PyValue::Str(a), PyValue::Str(b)) => a == b,
            (PyValue::DateTime(a), PyValue::DateTime(b)) => a == b,
            (PyValue::List(a), PyValue::List(b)) => a.len() == b.len() && a.iter().zip(b).all(|(x, y)| x.py_eq(y)),
            (PyValue::Dict(a), PyValue::Dict(b)) => {
                a.len() == b.len() && a.iter().all(|(k, v)| b.iter().any(|(k2, v2)| k.py_eq(k2) && v.py_eq(v2)))
            }
            _ => false,
        }
    }

    /// Python truthiness.
    pub fn truthy(&self) -> bool {
        match self {
            PyValue::None => false,
            PyValue::Bool(b) => *b,
            PyValue::Int(i) => *i != 0,
            PyValue::Float(f) => *f != 0.0,
            PyValue::Str(s) => !s.is_empty(),
            PyValue::List(l) => !l.is_empty(),
            PyValue::Dict(d) => !d.is_empty(),
            PyValue::DateTime(_) => true,
        }
    }

    pub fn hashable(&self) -> bool {
        !matches!(self, PyValue::List(_) | PyValue::Dict(_))
    }

    fn require_hashable(&self) -> Py<()> {
        if self.hashable() {
            Ok(())
        } else {
            Err(Raised::type_error(format!("unhashable type: '{}'", self.type_name())))
        }
    }

    /// `d[key]`.
    pub(crate) fn getitem(&self, key: &PyValue) -> Py<PyValue> {
        match self {
            PyValue::Dict(entries) => {
                key.require_hashable()?;
                entries
                    .iter()
                    .find(|(k, _)| k.py_eq(key))
                    .map(|(_, v)| v.clone())
                    .ok_or_else(|| Raised::key(key.py_str()))
            }
            PyValue::List(items) => match key.num() {
                Some(Num::Int(i)) if !matches!(key, PyValue::Float(_)) => {
                    let n = items.len() as i128;
                    let idx = if i < 0 { i + n } else { i };
                    if (0..n).contains(&idx) {
                        Ok(items[idx as usize].clone())
                    } else {
                        Err(Raised::Other { name: "IndexError".into(), detail: "list index out of range".into() })
                    }
                }
                _ => {
                    Err(Raised::type_error(format!("list indices must be integers or slices, not {}", key.type_name())))
                }
            },
            PyValue::Str(s) => match key {
                PyValue::Int(_) | PyValue::Bool(_) => {
                    let i = match key.num() {
                        Some(Num::Int(i)) => i,
                        _ => unreachable!("Int or Bool"),
                    };
                    let chars: Vec<char> = s.chars().collect();
                    let n = chars.len() as i128;
                    let idx = if i < 0 { i + n } else { i };
                    if (0..n).contains(&idx) {
                        Ok(PyValue::Str(chars[idx as usize].to_string()))
                    } else {
                        Err(Raised::Other { name: "IndexError".into(), detail: "string index out of range".into() })
                    }
                }
                _ => Err(Raised::type_error(format!("string indices must be integers, not '{}'", key.type_name()))),
            },
            _ => Err(Raised::type_error(format!("'{}' object is not subscriptable", self.type_name()))),
        }
    }

    pub(crate) fn getitem_str(&self, key: &str) -> Py<PyValue> {
        self.getitem(&PyValue::str(key))
    }

    /// `d.get(key)` (None when absent); AttributeError (TYPE_ERROR) when `d` is not a dict.
    pub(crate) fn get(&self, key: &str) -> Py<Option<PyValue>> {
        match self {
            PyValue::Dict(entries) => {
                Ok(entries.iter().find(|(k, _)| matches!(k, PyValue::Str(s) if s == key)).map(|(_, v)| v.clone()))
            }
            _ => Err(Raised::type_error(format!("'{}' object has no attribute 'get'", self.type_name()))),
        }
    }

    /// `d.items()` of a dict; AttributeError (TYPE_ERROR) otherwise.
    pub(crate) fn items(&self) -> Py<Vec<(PyValue, PyValue)>> {
        match self {
            PyValue::Dict(entries) => Ok(entries.clone()),
            _ => Err(Raised::type_error(format!("'{}' object has no attribute 'items'", self.type_name()))),
        }
    }

    /// `for x in v`: list elements, dict keys, string characters.
    pub(crate) fn iterate(&self) -> Py<Vec<PyValue>> {
        match self {
            PyValue::List(items) => Ok(items.clone()),
            PyValue::Dict(entries) => Ok(entries.iter().map(|(k, _)| k.clone()).collect()),
            PyValue::Str(s) => Ok(s.chars().map(|c| PyValue::Str(c.to_string())).collect()),
            _ => Err(Raised::type_error(format!("'{}' object is not iterable", self.type_name()))),
        }
    }

    /// `len(v)`.
    pub(crate) fn py_len(&self) -> Py<usize> {
        match self {
            PyValue::List(items) => Ok(items.len()),
            PyValue::Dict(entries) => Ok(entries.len()),
            PyValue::Str(s) => Ok(s.chars().count()),
            _ => Err(Raised::type_error(format!("object of type '{}' has no len()", self.type_name()))),
        }
    }

    /// `item in self`.
    pub(crate) fn contains(&self, item: &PyValue) -> Py<bool> {
        match self {
            PyValue::Str(s) => match item {
                PyValue::Str(needle) => Ok(s.contains(needle.as_str())),
                _ => Err(Raised::type_error(format!(
                    "'in <string>' requires string as left operand, not {}",
                    item.type_name()
                ))),
            },
            PyValue::List(items) => Ok(items.iter().any(|x| x.py_eq(item))),
            PyValue::Dict(entries) => {
                item.require_hashable()?;
                Ok(entries.iter().any(|(k, _)| k.py_eq(item)))
            }
            _ => Err(Raised::type_error(format!("argument of type '{}' is not iterable", self.type_name()))),
        }
    }

    /// `float(v)`.
    pub(crate) fn py_float(&self) -> Py<f64> {
        match self {
            PyValue::Bool(b) => Ok(f64::from(u8::from(*b))),
            PyValue::Int(i) => Ok(*i as f64),
            PyValue::Float(f) => Ok(*f),
            PyValue::Str(s) => float_from_str(s)
                .ok_or_else(|| Raised::Value { detail: format!("could not convert string to float: {s:?}") }),
            _ => Err(Raised::type_error(format!(
                "float() argument must be a string or a real number, not '{}'",
                self.type_name()
            ))),
        }
    }

    /// Python `str(v)` for scalars (containers and datetimes: a stable text, used only in details).
    pub fn py_str(&self) -> String {
        match self {
            PyValue::None => "None".into(),
            PyValue::Bool(true) => "True".into(),
            PyValue::Bool(false) => "False".into(),
            PyValue::Int(i) => i.to_string(),
            PyValue::Float(f) => float_repr(*f),
            PyValue::Str(s) => s.clone(),
            PyValue::DateTime(s) => s.clone(),
            PyValue::List(_) | PyValue::Dict(_) => format!("<{}>", self.type_name()),
        }
    }

    /// Compact JSON of a scalar or container (`json.dumps(v, separators=(",", ":"), ensure_ascii=False)`).
    pub fn to_compact_json(&self) -> String {
        match self {
            PyValue::None => "null".into(),
            PyValue::Bool(b) => b.to_string(),
            PyValue::Int(i) => i.to_string(),
            PyValue::Float(f) if f.is_nan() => "NaN".into(),
            PyValue::Float(f) if f.is_infinite() => if *f > 0.0 { "Infinity" } else { "-Infinity" }.into(),
            PyValue::Float(f) => float_repr(*f),
            PyValue::Str(s) | PyValue::DateTime(s) => serde_json::to_string(s).unwrap_or_default(),
            PyValue::List(items) => {
                format!("[{}]", items.iter().map(PyValue::to_compact_json).collect::<Vec<_>>().join(","))
            }
            PyValue::Dict(entries) => format!(
                "{{{}}}",
                entries
                    .iter()
                    .map(|(k, v)| format!("{}:{}", PyValue::str(k.py_str()).to_compact_json(), v.to_compact_json()))
                    .collect::<Vec<_>>()
                    .join(",")
            ),
        }
    }

    /// From a TOML document value (tomllib types).
    pub fn from_toml(v: &toml::Value) -> PyValue {
        match v {
            toml::Value::String(s) => PyValue::Str(s.clone()),
            toml::Value::Integer(i) => PyValue::Int(i128::from(*i)),
            toml::Value::Float(f) => PyValue::Float(*f),
            toml::Value::Boolean(b) => PyValue::Bool(*b),
            toml::Value::Datetime(d) => PyValue::DateTime(d.to_string()),
            toml::Value::Array(a) => PyValue::List(a.iter().map(PyValue::from_toml).collect()),
            toml::Value::Table(t) => {
                PyValue::Dict(t.iter().map(|(k, v)| (PyValue::Str(k.clone()), PyValue::from_toml(v))).collect())
            }
        }
    }
}

/// `math.isclose(a, b, rel_tol=rel, abs_tol=0.0)`, operation for operation.
pub fn isclose(a: f64, b: f64, rel: f64) -> bool {
    if a == b {
        return true;
    }
    if a.is_infinite() || b.is_infinite() {
        return false;
    }
    let diff = (b - a).abs();
    diff <= (rel * b).abs() || diff <= (rel * a).abs()
}

/// Python `float(str)`: surrounding whitespace, an optional sign, inf / infinity / nan (any case), decimal digits with
/// single underscores between digits, optional fraction and exponent. `None` is a ValueError.
pub fn float_from_str(s: &str) -> Option<f64> {
    let t = s.trim();
    let (neg, body) = match t.as_bytes().first() {
        Some(b'-') => (true, &t[1..]),
        Some(b'+') => (false, &t[1..]),
        _ => (false, t),
    };
    let lower = body.to_ascii_lowercase();
    let special = match lower.as_str() {
        "inf" | "infinity" => Some(f64::INFINITY),
        "nan" => Some(f64::NAN),
        _ => None,
    };
    if let Some(v) = special {
        return Some(if neg { -v } else { v });
    }
    let bytes = body.as_bytes();
    for (i, &c) in bytes.iter().enumerate() {
        if c == b'_' {
            let before = i > 0 && bytes[i - 1].is_ascii_digit();
            let after = bytes.get(i + 1).is_some_and(u8::is_ascii_digit);
            if !(before && after) {
                return None;
            }
        }
    }
    let cleaned: String = body.chars().filter(|&c| c != '_').collect();
    if !decimal_float_grammar(&cleaned) {
        return None;
    }
    let v: f64 = cleaned.parse().ok()?;
    Some(if neg { -v } else { v })
}

/// `digits [. digits?] | . digits`, then an optional `e[+-]digits`.
pub(crate) fn decimal_float_grammar(s: &str) -> bool {
    let b = s.as_bytes();
    let mut i = 0;
    let int_digits = b.iter().take_while(|c| c.is_ascii_digit()).count();
    i += int_digits;
    let mut frac_digits = 0;
    if b.get(i) == Some(&b'.') {
        i += 1;
        frac_digits = b[i..].iter().take_while(|c| c.is_ascii_digit()).count();
        i += frac_digits;
    }
    if int_digits + frac_digits == 0 {
        return false;
    }
    if matches!(b.get(i), Some(b'e') | Some(b'E')) {
        i += 1;
        if matches!(b.get(i), Some(b'+') | Some(b'-')) {
            i += 1;
        }
        let exp_digits = b[i..].iter().take_while(|c| c.is_ascii_digit()).count();
        if exp_digits == 0 {
            return false;
        }
        i += exp_digits;
    }
    i == b.len()
}

/// Python `repr(float)`: shortest round-trip digits; positional for decimal exponents -4 <= e < 16, else
/// `d.ddde+XX`.
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "nan".into();
    }
    if f.is_infinite() {
        return if f > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let sign = if f.is_sign_negative() { "-" } else { "" };
    if f == 0.0 {
        return format!("{sign}0.0");
    }
    let sci = format!("{:e}", f.abs());
    let (mant, exp) = sci.split_once('e').unwrap_or((sci.as_str(), "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let n = digits.len() as i32;
    let body = if (-4..16).contains(&exp) {
        if exp >= 0 {
            let int_len = exp + 1;
            if n <= int_len {
                format!("{}{}.0", digits, "0".repeat((int_len - n) as usize))
            } else {
                format!("{}.{}", &digits[..int_len as usize], &digits[int_len as usize..])
            }
        } else {
            format!("0.{}{}", "0".repeat((-exp - 1) as usize), digits)
        }
    } else {
        let m = if n > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.clone() };
        format!("{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    format!("{sign}{body}")
}

impl<'de> Deserialize<'de> for PyValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_any(PyValueVisitor)
    }
}

struct PyValueVisitor;

impl<'de> Visitor<'de> for PyValueVisitor {
    type Value = PyValue;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value")
    }

    fn visit_bool<E: de::Error>(self, v: bool) -> Result<PyValue, E> {
        Ok(PyValue::Bool(v))
    }

    fn visit_i64<E: de::Error>(self, v: i64) -> Result<PyValue, E> {
        Ok(PyValue::Int(i128::from(v)))
    }

    fn visit_u64<E: de::Error>(self, v: u64) -> Result<PyValue, E> {
        Ok(PyValue::Int(i128::from(v)))
    }

    fn visit_f64<E: de::Error>(self, v: f64) -> Result<PyValue, E> {
        Ok(PyValue::Float(v))
    }

    fn visit_str<E: de::Error>(self, v: &str) -> Result<PyValue, E> {
        Ok(PyValue::Str(v.to_owned()))
    }

    fn visit_string<E: de::Error>(self, v: String) -> Result<PyValue, E> {
        Ok(PyValue::Str(v))
    }

    fn visit_unit<E: de::Error>(self) -> Result<PyValue, E> {
        Ok(PyValue::None)
    }

    fn visit_none<E: de::Error>(self) -> Result<PyValue, E> {
        Ok(PyValue::None)
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<PyValue, A::Error> {
        let mut items = Vec::new();
        while let Some(v) = seq.next_element::<PyValue>()? {
            items.push(v);
        }
        Ok(PyValue::List(items))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<PyValue, A::Error> {
        let mut entries: Vec<(PyValue, PyValue)> = Vec::new();
        while let Some((k, v)) = map.next_entry::<String, PyValue>()? {
            match entries.iter_mut().find(|(ek, _)| matches!(ek, PyValue::Str(s) if *s == k)) {
                Some(slot) => slot.1 = v,
                None => entries.push((PyValue::Str(k), v)),
            }
        }
        Ok(PyValue::Dict(entries))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn json(s: &str) -> PyValue {
        serde_json::from_str(s).unwrap()
    }

    #[test]
    fn json_objects_keep_file_order_and_python_duplicate_rule() {
        let v = json(r#"{"b": 1, "a": 2, "b": 3}"#);
        match &v {
            PyValue::Dict(e) => {
                assert_eq!(e.len(), 2);
                assert_eq!(e[0], (PyValue::str("b"), PyValue::Int(3)));
                assert_eq!(e[1], (PyValue::str("a"), PyValue::Int(2)));
            }
            other => panic!("{other:?}"),
        }
        assert!(matches!(json("6"), PyValue::Int(6)));
        assert!(matches!(json("6.0"), PyValue::Float(_)));
    }

    #[test]
    fn python_equality_and_isclose() {
        assert!(PyValue::Int(2).py_eq(&PyValue::Float(2.0)));
        assert!(PyValue::Bool(true).py_eq(&PyValue::Int(1)));
        assert!(!PyValue::Int(2).py_eq(&PyValue::Float(2.5)));
        assert!(!PyValue::str("1").py_eq(&PyValue::Int(1)));
        assert!(json("[0.005, 1]").py_eq(&json("[0.005, 1.0]")));
        assert!(json(r#"{"a": 1, "b": 2}"#).py_eq(&json(r#"{"b": 2, "a": 1}"#)));
        assert!(isclose(1.0, 1.0 + 1e-10, 1e-9));
        assert!(!isclose(1.0, 1.0 + 1e-8, 1e-9));
        assert!(!isclose(f64::INFINITY, 1.0, 1e-9));
        assert!(isclose(f64::INFINITY, f64::INFINITY, 1e-9));
        assert!(!isclose(f64::NAN, f64::NAN, 1e-9));
        assert!(!isclose(0.0, 1e-300, 1e-9));
    }

    #[test]
    fn subscription_errors_are_python_errors() {
        let d = json(r#"{"a": [1, 2], "s": "xy"}"#);
        assert_eq!(d.getitem_str("missing").unwrap_err(), Raised::key("missing"));
        assert!(matches!(d.getitem_str("a").unwrap().getitem_str("k"), Err(Raised::Type { .. })));
        assert_eq!(d.getitem_str("a").unwrap().getitem(&PyValue::Int(-1)).unwrap(), PyValue::Int(2));
        assert!(matches!(PyValue::Int(3).getitem_str("k"), Err(Raised::Type { .. })));
        assert!(matches!(PyValue::List(vec![]).get("k"), Err(Raised::Type { .. })));
        assert!(matches!(d.getitem(&PyValue::List(vec![])), Err(Raised::Type { .. })));
        assert_eq!(d.get("zz").unwrap(), None);
        assert!(json(r#""a 0.42-0.60 b""#).contains(&PyValue::str("0.42-0.60")).unwrap());
        assert!(matches!(PyValue::Int(1).contains(&PyValue::str("x")), Err(Raised::Type { .. })));
        assert!(!d.truthy() || d.py_len().unwrap() == 2);
    }

    #[test]
    fn float_from_str_follows_python() {
        for (s, want) in [("0.005", Some(0.005)), (" 1e-3 ", Some(1e-3)), ("1_000.5", Some(1000.5)), (".5", Some(0.5))]
        {
            assert_eq!(float_from_str(s), want, "{s}");
        }
        assert_eq!(float_from_str("5."), Some(5.0));
        assert!(float_from_str("-Infinity").unwrap().is_infinite());
        assert!(float_from_str("nan").unwrap().is_nan());
        for s in ["not-a-number", "", "1__0", "_1", "1_", "1e", "0x10", "1.2.3", "e5"] {
            assert_eq!(float_from_str(s), None, "{s}");
        }
    }

    #[test]
    fn float_repr_matches_python() {
        for (f, want) in [
            (1.380649e-23, "1.380649e-23"),
            (1500.0, "1500.0"),
            (12.5, "12.5"),
            (0.001, "0.001"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1e16, "1e+16"),
            (1234567890123456.0, "1234567890123456.0"),
            (-0.0, "-0.0"),
            (0.1 + 0.2, "0.30000000000000004"),
            (1.5e300, "1.5e+300"),
        ] {
            assert_eq!(float_repr(f), want);
        }
        assert_eq!(PyValue::List(vec![PyValue::str("a\"b"), PyValue::Int(1)]).to_compact_json(), r#"["a\"b",1]"#);
    }
}
