//! Accessors on the insertion-ordered Python-shaped JSON value (`abep_types::pyjson::Value`, the shape `json.loads`
//! produces). The design records keep the reference key order wherever an output depends on dict iteration order.

use abep_types::pyjson::{Dict, Value};

pub trait Pv<'a>: Copy {
    fn g(self, key: &str) -> Option<&'a Value>;
    fn arr(self) -> Option<&'a [Value]>;
    fn obj(self) -> Option<&'a Dict>;
    fn u(self) -> Option<u64>;
    fn f(self) -> Option<f64>;
    fn b(self) -> Option<bool>;
    fn s(self) -> Option<&'a str>;
    /// JSON-pointer style path `/a/b/0`.
    fn ptr(self, path: &str) -> Option<&'a Value>;
}

impl<'a> Pv<'a> for &'a Value {
    fn g(self, key: &str) -> Option<&'a Value> {
        self.as_dict().and_then(|d| d.get(key))
    }
    fn arr(self) -> Option<&'a [Value]> {
        self.as_list()
    }
    fn obj(self) -> Option<&'a Dict> {
        self.as_dict()
    }
    fn u(self) -> Option<u64> {
        match self {
            Value::Int(i) => i.as_i64().and_then(|x| u64::try_from(x).ok()),
            _ => None,
        }
    }
    fn f(self) -> Option<f64> {
        match self {
            Value::Int(i) => i.to_f64().ok(),
            Value::Float(x) => Some(*x),
            _ => None,
        }
    }
    fn b(self) -> Option<bool> {
        match self {
            Value::Bool(b) => Some(*b),
            _ => None,
        }
    }
    fn s(self) -> Option<&'a str> {
        self.as_str()
    }
    fn ptr(self, path: &str) -> Option<&'a Value> {
        let mut v = self;
        for part in path.split('/').filter(|p| !p.is_empty()) {
            v = match v {
                Value::Dict(d) => d.get(part)?,
                Value::List(l) => l.get(part.parse::<usize>().ok()?)?,
                _ => return None,
            };
        }
        Some(v)
    }
}

impl<'a> Pv<'a> for Option<&'a Value> {
    fn g(self, key: &str) -> Option<&'a Value> {
        self.and_then(|v| v.g(key))
    }
    fn arr(self) -> Option<&'a [Value]> {
        self.and_then(|v| v.arr())
    }
    fn obj(self) -> Option<&'a Dict> {
        self.and_then(|v| v.obj())
    }
    fn u(self) -> Option<u64> {
        self.and_then(|v| v.u())
    }
    fn f(self) -> Option<f64> {
        self.and_then(|v| v.f())
    }
    fn b(self) -> Option<bool> {
        self.and_then(|v| v.b())
    }
    fn s(self) -> Option<&'a str> {
        self.and_then(|v| v.s())
    }
    fn ptr(self, path: &str) -> Option<&'a Value> {
        self.and_then(|v| v.ptr(path))
    }
}

/// serde_json value of a pyjson value (dict key order is not preserved by serde_json maps).
pub fn to_serde(v: &Value) -> serde_json::Value {
    match v {
        Value::Null => serde_json::Value::Null,
        Value::Bool(b) => serde_json::Value::Bool(*b),
        Value::Int(i) => match i.as_i64() {
            Some(x) => serde_json::Value::from(x),
            None => serde_json::Value::from(i.to_f64().unwrap_or(f64::NAN)),
        },
        Value::Float(x) => abep_gaspath::rec::fnum(*x),
        Value::Str(s) => serde_json::Value::String(s.clone()),
        Value::List(l) => serde_json::Value::Array(l.iter().map(to_serde).collect()),
        Value::Dict(d) => serde_json::Value::Object(d.iter().map(|(k, v)| (k.clone(), to_serde(v))).collect()),
    }
}

/// pyjson value of a serde_json value (non-finite strings "NaN" / "+inf" / "-inf" stay strings).
pub fn from_serde(v: &serde_json::Value) -> Value {
    match v {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(b) => Value::Bool(*b),
        serde_json::Value::Number(n) => match n.as_i64() {
            Some(i) if !n.is_f64() => Value::int(i),
            _ => Value::Float(n.as_f64().unwrap_or(f64::NAN)),
        },
        serde_json::Value::String(s) => Value::Str(s.clone()),
        serde_json::Value::Array(a) => Value::List(a.iter().map(from_serde).collect()),
        serde_json::Value::Object(o) => Value::Dict(o.iter().map(|(k, v)| (k.clone(), from_serde(v))).collect()),
    }
}
