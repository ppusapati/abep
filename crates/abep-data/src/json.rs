//! Order-preserving JSON value and the reference's structural comparison.
//!
//! `serde_json::Value` sorts object keys; the reference compares key order (`atmosphere_orbit._design_v2_compare`:
//! `list(a) != list(b)`), so documents are read into [`OValue`], which keeps keys in file order and distinguishes JSON
//! integers from floats as Python's `json` module does.

use abep_types::{AbepError, AbepResult};
use serde::de::{Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub enum OValue {
    Null,
    Bool(bool),
    Int(i128),
    Float(f64),
    Str(String),
    Array(Vec<OValue>),
    Object(Vec<(String, OValue)>),
}

impl OValue {
    pub fn parse(bytes: &[u8], path: &str) -> AbepResult<OValue> {
        serde_json::from_slice(bytes)
            .map_err(|e| AbepError::Schema { path: path.to_string(), message: format!("invalid JSON: {e}") })
    }

    /// Member of an object (first occurrence).
    pub fn get(&self, key: &str) -> Option<&OValue> {
        match self {
            OValue::Object(m) => m.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            OValue::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_array(&self) -> Option<&[OValue]> {
        match self {
            OValue::Array(a) => Some(a),
            _ => None,
        }
    }

    /// A JSON number (integer or float) as f64; booleans are not numbers.
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            OValue::Int(i) => Some(*i as f64),
            OValue::Float(f) => Some(*f),
            _ => None,
        }
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            OValue::Bool(b) => Some(*b),
            _ => None,
        }
    }
}

impl<'de> Deserialize<'de> for OValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_any(OVisitor)
    }
}

struct OVisitor;

impl<'de> Visitor<'de> for OVisitor {
    type Value = OValue;

    fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str("a JSON value")
    }
    fn visit_bool<E>(self, v: bool) -> Result<OValue, E> {
        Ok(OValue::Bool(v))
    }
    fn visit_i64<E>(self, v: i64) -> Result<OValue, E> {
        Ok(OValue::Int(v as i128))
    }
    fn visit_u64<E>(self, v: u64) -> Result<OValue, E> {
        Ok(OValue::Int(v as i128))
    }
    fn visit_f64<E>(self, v: f64) -> Result<OValue, E> {
        Ok(OValue::Float(v))
    }
    fn visit_str<E>(self, v: &str) -> Result<OValue, E> {
        Ok(OValue::Str(v.to_string()))
    }
    fn visit_string<E>(self, v: String) -> Result<OValue, E> {
        Ok(OValue::Str(v))
    }
    fn visit_unit<E>(self) -> Result<OValue, E> {
        Ok(OValue::Null)
    }
    fn visit_none<E>(self) -> Result<OValue, E> {
        Ok(OValue::Null)
    }
    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<OValue, A::Error> {
        let mut v = Vec::new();
        while let Some(x) = seq.next_element()? {
            v.push(x);
        }
        Ok(OValue::Array(v))
    }
    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<OValue, A::Error> {
        let mut v: Vec<(String, OValue)> = Vec::new();
        while let Some((k, x)) = map.next_entry::<String, OValue>()? {
            v.push((k, x));
        }
        Ok(OValue::Object(v))
    }
}

/// Result of [`compare_documents`].
#[derive(Debug, Clone, PartialEq)]
pub struct Comparison {
    pub exact_mismatches: Vec<String>,
    pub floats_differing: usize,
    pub max_abs_rel_diff: f64,
    pub rel_tol: f64,
    pub ok: bool,
}

/// `atmosphere_orbit._design_v2_compare`: structure, key order, lengths and every non-float leaf exact (type
/// included: int != float); floats within `rel_tol` relative (|a - b| / max(|a|, |b|)).
pub fn compare_documents(frozen: &OValue, fresh: &OValue, rel_tol: f64) -> Comparison {
    let mut c =
        Comparison { exact_mismatches: Vec::new(), floats_differing: 0, max_abs_rel_diff: 0.0, rel_tol, ok: false };
    walk(frozen, fresh, "", &mut c);
    c.ok = c.exact_mismatches.is_empty() && c.max_abs_rel_diff <= rel_tol;
    c
}

fn walk(a: &OValue, b: &OValue, path: &str, c: &mut Comparison) {
    match (a, b) {
        (OValue::Object(x), OValue::Object(y)) => {
            if x.len() != y.len() || x.iter().zip(y).any(|((ka, _), (kb, _))| ka != kb) {
                c.exact_mismatches.push(format!("{path}: keys differ"));
                return;
            }
            for ((k, va), (_, vb)) in x.iter().zip(y) {
                walk(va, vb, &format!("{path}.{k}"), c);
            }
        }
        (OValue::Array(x), OValue::Array(y)) => {
            if x.len() != y.len() {
                c.exact_mismatches.push(format!("{path}: length {} != {}", x.len(), y.len()));
                return;
            }
            for (i, (va, vb)) in x.iter().zip(y).enumerate() {
                walk(va, vb, &format!("{path}[{i}]"), c);
            }
        }
        (OValue::Float(x), OValue::Float(y)) => {
            if x != y {
                c.floats_differing += 1;
                let d =
                    if x.is_finite() && y.is_finite() { (x - y).abs() / x.abs().max(y.abs()) } else { f64::INFINITY };
                c.max_abs_rel_diff = c.max_abs_rel_diff.max(d);
            }
        }
        _ => {
            if a != b {
                let mut m = format!("{path}: {a:?} != {b:?}");
                m.truncate(200);
                c.exact_mismatches.push(m);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_key_order_and_number_kinds() {
        let v = OValue::parse(br#"{"b": 1, "a": 1.0, "c": [true, null, "x"]}"#, "t").unwrap();
        match &v {
            OValue::Object(m) => {
                assert_eq!(m.iter().map(|(k, _)| k.as_str()).collect::<Vec<_>>(), ["b", "a", "c"]);
                assert_eq!(m[0].1, OValue::Int(1));
                assert_eq!(m[1].1, OValue::Float(1.0));
            }
            _ => panic!(),
        }
    }

    #[test]
    fn comparison_semantics() {
        let a = OValue::parse(br#"{"x": 1.0, "n": 2, "s": "a"}"#, "t").unwrap();
        let b = OValue::parse(br#"{"x": 1.0000000000001, "n": 2, "s": "a"}"#, "t").unwrap();
        let c = compare_documents(&a, &b, 1e-12);
        assert!(c.ok && c.floats_differing == 1);
        let d = OValue::parse(br#"{"x": 1.0, "n": 2.0, "s": "a"}"#, "t").unwrap();
        assert!(!compare_documents(&a, &d, 1e-12).ok, "int vs float is an exact mismatch");
        let e = OValue::parse(br#"{"n": 2, "x": 1.0, "s": "a"}"#, "t").unwrap();
        assert!(!compare_documents(&a, &e, 1e-12).ok, "key order is compared");
    }
}
